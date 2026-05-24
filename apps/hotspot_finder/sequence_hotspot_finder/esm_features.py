from __future__ import annotations
import math
import numpy as np
import pandas as pd

AA_LIST = list("ACDEFGHIKLMNPQRSTVWY")


def segment_ranges(seq_len: int, window: int = 900, overlap: int = 150, domains_df=None, record_name: str | None = None) -> list[dict]:
    """Domain-aware segmentation. Domains longer than window are sub-windowed."""
    if seq_len <= 0:
        return []
    window = int(window)
    overlap = int(overlap)
    if window <= overlap:
        raise ValueError("window must be greater than overlap")
    base_segments = []
    if domains_df is not None and not domains_df.empty and record_name is not None and "record_name" in domains_df:
        sub = domains_df[domains_df["record_name"].astype(str) == str(record_name)].copy()
        if not sub.empty:
            for _, r in sub.iterrows():
                s = max(1, int(r["start"]))
                e = min(seq_len, int(r["end"]))
                if e >= s:
                    base_segments.append({"start": s, "end": e, "domain_name": str(r.get("domain_name", "domain"))})
    if not base_segments:
        base_segments = [{"start": 1, "end": seq_len, "domain_name": "full_sequence"}]
    final = []
    step = window - overlap
    for seg in base_segments:
        s, e = seg["start"], seg["end"]
        length = e - s + 1
        if length <= window:
            final.append({**seg, "window_start": s, "window_end": e})
        else:
            cur = s
            part = 1
            while cur <= e:
                w_end = min(e, cur + window - 1)
                final.append({"start": s, "end": e, "domain_name": seg["domain_name"], "window_start": cur, "window_end": w_end, "window_part": part})
                if w_end >= e:
                    break
                cur += step
                part += 1
    return final


class ESMFeatureExtractor:
    def __init__(self, model_name: str = "esm2_t6_8M_UR50D", device: str = "auto"):
        self.model_name = model_name
        self.device = device
        self.model = None
        self.alphabet = None
        self.batch_converter = None
        self.torch = None

    def load(self):
        import torch
        import esm
        self.torch = torch
        if self.device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model, self.alphabet = getattr(esm.pretrained, self.model_name)()
        self.model = self.model.eval().to(self.device)
        self.batch_converter = self.alphabet.get_batch_converter()
        return self

    def _forward(self, name: str, seq: str, repr_layer: int = None):
        torch = self.torch
        if repr_layer is None:
            # t6/t12/t30 name convention
            if "t6" in self.model_name: repr_layer = 6
            elif "t12" in self.model_name: repr_layer = 12
            elif "t30" in self.model_name: repr_layer = 30
            else: repr_layer = 6
        _, _, toks = self.batch_converter([(name, seq)])
        toks = toks.to(self.device)
        with torch.no_grad():
            out = self.model(toks, repr_layers=[repr_layer], return_contacts=False)
        return toks, out, repr_layer

    def embedding_norm(self, seq: str, name="seq") -> np.ndarray:
        toks, out, layer = self._forward(name, seq)
        rep = out["representations"][layer][0, 1:len(seq)+1]
        vals = rep.norm(dim=-1).detach().cpu().numpy()
        return vals

    def masked_features(self, seq: str, name="seq", batch_size: int = 4, use_mutation_sensitivity: bool = True, max_mutation_scan_length: int = 2500):
        torch = self.torch
        n = len(seq)
        log_probs_wt = np.full(n, np.nan, dtype=float)
        mut_sens = np.full(n, np.nan, dtype=float)
        if n == 0:
            return log_probs_wt, mut_sens
        if n > int(max_mutation_scan_length):
            use_mutation_sensitivity = False
        data = [(f"{name}_{i}", seq) for i in range(n)]
        _, _, toks = self.batch_converter(data)
        mask_idx = self.alphabet.mask_idx
        aa_to_idx = {aa: self.alphabet.get_idx(aa) for aa in AA_LIST}
        wt_indices = [aa_to_idx.get(a, None) for a in seq]
        for start in range(0, n, batch_size):
            end = min(n, start+batch_size)
            batch = toks[start:end].clone()
            for j, pos in enumerate(range(start, end)):
                batch[j, pos+1] = mask_idx
            batch = batch.to(self.device)
            with torch.no_grad():
                logits = self.model(batch)["logits"]
                logp = torch.log_softmax(logits[:, 1:n+1, :], dim=-1).detach().cpu().numpy()
            for j, pos in enumerate(range(start, end)):
                wt_idx = wt_indices[pos]
                if wt_idx is None:
                    continue
                dist = logp[j, pos, :]
                log_probs_wt[pos] = dist[wt_idx]
                if use_mutation_sensitivity:
                    aa_vals = np.array([dist[aa_to_idx[a]] for a in AA_LIST if aa_to_idx[a] != wt_idx], dtype=float)
                    mut_sens[pos] = max(0.0, float(dist[wt_idx] - np.mean(aa_vals)))
        return log_probs_wt, mut_sens


def normalize_array(x):
    x = np.asarray(x, dtype=float)
    mask = np.isfinite(x)
    out = np.zeros_like(x, dtype=float)
    if mask.sum() == 0:
        return out
    mn, mx = np.nanmin(x[mask]), np.nanmax(x[mask])
    if abs(mx-mn) < 1e-12:
        out[mask] = 0.0
    else:
        out[mask] = (x[mask]-mn)/(mx-mn)
    return out


def compute_esm_features_for_model_sequence(model_sequence: str, config: dict, domains_df=None, record_name: str | None = None) -> pd.DataFrame:
    n = len(model_sequence)
    if n == 0:
        return pd.DataFrame(columns=["model_position"])
    window = int(config.get("window_size", 900))
    safe_limit = int(config.get("safe_window_limit", 1000))
    if config.get("clamp_window_size", True) and window > safe_limit:
        window = safe_limit
    overlap = int(config.get("overlap", 150))
    batch_size = int(config.get("batch_size", 4))
    extractor = ESMFeatureExtractor(config.get("esm_model", "esm2_t6_8M_UR50D"), config.get("device", "auto")).load()
    segments = segment_ranges(n, window=window, overlap=overlap, domains_df=domains_df, record_name=record_name)
    emb_sum = np.zeros(n); unpred_sum = np.zeros(n); mut_sum = np.zeros(n); cov = np.zeros(n)
    raw_log_sum = np.zeros(n)
    for k, seg in enumerate(segments):
        ws, we = int(seg["window_start"]), int(seg["window_end"])
        sub = model_sequence[ws-1:we]
        emb = extractor.embedding_norm(sub, name=f"{record_name or 'seq'}_w{k}")
        logp, mut = extractor.masked_features(sub, name=f"{record_name or 'seq'}_w{k}", batch_size=batch_size,
                                              use_mutation_sensitivity=bool(config.get("use_mutation_sensitivity", True)),
                                              max_mutation_scan_length=int(config.get("max_mutation_scan_length", 2500))) if config.get("use_masked_marginal", True) else (np.full(len(sub), np.nan), np.full(len(sub), np.nan))
        emb_n = normalize_array(emb)
        unpred = normalize_array(-logp) if np.isfinite(logp).any() else np.zeros(len(sub))
        mut_n = normalize_array(mut) if np.isfinite(mut).any() else np.zeros(len(sub))
        idx = np.arange(ws-1, we)
        emb_sum[idx] += emb_n
        unpred_sum[idx] += unpred
        mut_sum[idx] += mut_n
        raw_log_sum[idx] += np.nan_to_num(logp, nan=0.0)
        cov[idx] += 1
    cov_safe = np.where(cov == 0, 1, cov)
    df = pd.DataFrame({
        "model_position": np.arange(1, n+1),
        "esm_embedding_score": emb_sum / cov_safe,
        "esm_unpredictability_score": unpred_sum / cov_safe,
        "esm_mutation_sensitivity": mut_sum / cov_safe,
        "esm_masked_log_prob": raw_log_sum / cov_safe,
        "esm_window_coverage": cov,
    })
    return df
