"""Classic Batch/Project UI behavior for embedded SPPS Planner V5.

This mixin contains the accepted Batch Manager presentation and Project Manager
live-sync overrides.  It replaces the historical version-suffixed function/alias
stack with normal class methods resolved by Python inheritance.
"""
from __future__ import annotations

import math
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from peptiforg_core.lazy_imports import lazy_module

pd = lazy_module("pandas")

from spps_v4_gui.gui_primitives import const_var


class ClassicBatchControllerMixin:
    """Focused Batch/Project behavior layered above ``ClassicBaseCore``."""

    @staticmethod
    def _is_blank(value):
        try:
            if value is None or pd.isna(value):
                return True
        except Exception:
            pass
        return str(value).strip().lower() in {"", "nan", "none", "nat", "<na>"}

    @classmethod
    def _display_to_float(cls, value):
        try:
            if cls._is_blank(value):
                return None
            number = float(str(value).replace(",", "").strip())
            return number if math.isfinite(number) else None
        except Exception:
            return None

    def _roundup_ml(self, calc_ml: float) -> float:
        try:
            calc_ml = float(calc_ml or 0)
        except Exception:
            calc_ml = 0.0
        if calc_ml <= 0:
            return 0.0
        try:
            step = max(float(self.batch_actual_round_ml.get()), 1.0)
        except Exception:
            step = 10.0
        try:
            extra = max(float(self.batch_actual_extra_ml.get()), 0.0)
        except Exception:
            extra = 10.0
        import math
        return math.ceil(calc_ml / step) * step + extra

    def _project_rows(self):
        rows = []
        for item in list(getattr(self, 'pm_items', [])):
            seq = str(item.get('sequence', '') or '').strip()
            if not seq:
                continue
            rows.append({'Project': item.get('project', ''), 'Peptide name': item.get('peptide', ''), 'Sequence': seq, 'Copies': item.get('copies', '1') or '1', 'Scale mmol': item.get('scale', '0.2') or '0.2', 'Resin': item.get('resin', ''), 'Loading': item.get('loading', ''), 'LOT No': item.get('lot', ''), 'Chemistry': item.get('chemistry', 'DIC/HOBt') or 'DIC/HOBt'})
        return rows

    def _aa_calculator_df(self, rows=None):
        rows = rows if rows is not None else self._project_rows()
        try:
            conc = float(self.batch_solution_conc.get())
        except Exception:
            conc = 0.25
        try:
            aa_eq = float(self.batch_coupling_eq.get())
        except Exception:
            aa_eq = 10.0
        totals = {}
        for r in rows:
            try:
                copies = max(int(float(r.get('Copies', 1) or 1)), 1)
            except Exception:
                copies = 1
            try:
                scale = float(r.get('Scale mmol', 0.2) or 0.2)
            except Exception:
                scale = 0.2
            for aa in self._aa_letters_from_sequence(r.get('Sequence', '')):
                totals.setdefault(aa, {'count': 0, 'mmol': 0.0})
                totals[aa]['count'] += copies
                totals[aa]['mmol'] += copies * scale * aa_eq
        out = []
        for aa in sorted(totals):
            count = totals[aa]['count']
            mmol = totals[aa]['mmol']
            calc_ml = mmol / conc if conc else 0.0
            actual_ml = self._roundup_ml(calc_ml)
            mw = self._mw_for_token(aa) or self.MW_FALLBACK.get(aa, 0.0)
            weight_g = actual_ml / 1000.0 * conc * mw if actual_ml and conc and mw else 0.0
            out.append({'AA': aa, 'count': count, 'eq': aa_eq, 'solvent': 'DMF', 'conc_M': conc, 'calculated_mL': round(calc_ml, 2), 'actual_mL': round(actual_ml, 2), 'MW': round(mw, 2) if mw else 'manual', 'weight_g': round(weight_g, 2), 'note': 'synthesizer AA stock; actual includes transfer/dead-volume reserve'})
        return pd.DataFrame(out, columns=['AA', 'count', 'eq', 'solvent', 'conc_M', 'calculated_mL', 'actual_mL', 'MW', 'weight_g', 'note'])

    def _add_solution_record(self, d, item, purpose, count, eq, solvent, conc, mmol, note=''):
        item = str(item or '').strip()
        if not item:
            return
        key = (item, purpose, solvent, str(eq), str(conc))
        rec = d.setdefault(key, {'item': item, 'purpose': purpose, 'count': 0.0, 'eq': eq, 'solvent': solvent, 'conc_M': conc, 'mmol': 0.0, 'note': note})
        rec['count'] += float(count or 0)
        rec['mmol'] += float(mmol or 0)

    def _solution_records_to_df(self, d):
        out = []
        for rec in d.values():
            item = rec['item']
            conc = float(rec.get('conc_M') or 0) if str(rec.get('conc_M', '')).strip() else 0.0
            mmol = float(rec.get('mmol') or 0)
            mw = self._mw_for_token(item) or self.MW_FALLBACK.get(item, 0.0)
            density = self._density_for_token(item)
            calc_ml = mmol / conc if conc else 0.0
            actual_ml = self._roundup_ml(calc_ml) if calc_ml else 0.0
            if not conc:
                calc_g = mmol * mw / 1000.0 if mw else 0.0
                actual_g = round(calc_g * 1.1 + 0.004, 2) if calc_g else 0.0
                volume_ml = actual_g / density if density else ''
                out.append({'item': item, 'purpose': rec['purpose'], 'count': int(rec['count']) if float(rec['count']).is_integer() else round(rec['count'], 2), 'eq': rec['eq'], 'solvent': rec.get('solvent', ''), 'conc_M': '', 'calculated': '', 'actual': '', 'unit': 'g' if not density else 'g/mL', 'MW': round(mw, 2) if mw else 'manual', 'density': round(density, 3) if density else '', 'weight_g': actual_g if actual_g else '', 'volume_mL': round(volume_ml, 2) if isinstance(volume_ml, float) else volume_ml, 'note': rec.get('note', '')})
            else:
                weight_g = actual_ml / 1000.0 * conc * mw if actual_ml and mw else 0.0
                out.append({'item': item, 'purpose': rec['purpose'], 'count': int(rec['count']) if float(rec['count']).is_integer() else round(rec['count'], 2), 'eq': rec['eq'], 'solvent': rec.get('solvent', ''), 'conc_M': conc, 'calculated': round(calc_ml, 2), 'actual': round(actual_ml, 2), 'unit': 'mL', 'MW': round(mw, 2) if mw else 'manual', 'density': round(density, 3) if density else '', 'weight_g': round(weight_g, 2) if weight_g else '', 'volume_mL': round(actual_ml, 2), 'note': rec.get('note', '')})
        cols = ['item', 'purpose', 'count', 'eq', 'solvent', 'conc_M', 'calculated', 'actual', 'unit', 'MW', 'density', 'weight_g', 'volume_mL', 'note']
        return pd.DataFrame(out, columns=cols)

    def _batch_totals(self, rows=None):
        rows = rows if rows is not None else self._project_rows()
        coupling = {}
        catalyst = {}
        solvent = {}
        modifier = {}
        try:
            aa_eq = float(self.batch_coupling_eq.get())
        except Exception:
            aa_eq = 10.0
        try:
            hbtu_eq = float(self.batch_hbtu_eq.get())
        except Exception:
            hbtu_eq = 10.0
        try:
            hbtu_conc = float(self.batch_hbtu_conc.get())
        except Exception:
            hbtu_conc = 0.4
        for r in rows:
            try:
                copies = max(int(float(r.get('Copies', 1) or 1)), 1)
            except Exception:
                copies = 1
            try:
                scale = float(r.get('Scale mmol', 0.2) or 0.2)
            except Exception:
                scale = 0.2
            aas = self._aa_letters_from_sequence(r.get('Sequence', ''))
            steps = len(aas) * copies
            chem = str(r.get('Chemistry', 'DIC/HOBt') or 'DIC/HOBt')
            step_mmol = steps * scale
            if steps:
                if 'HBTU/NMP' in chem:
                    self._add_solution_record(coupling, 'HBTU', 'coupling reagent stock', steps, hbtu_eq, 'NMP', hbtu_conc, step_mmol * hbtu_eq, 'prepare HBTU/NMP stock for synthesizer bottle')
                    calc_ml = step_mmol * hbtu_eq / hbtu_conc if hbtu_conc else 0.0
                    self._add_solution_record(solvent, 'NMP', 'HBTU stock solvent', steps, '', '', 0, calc_ml, 'mL of NMP needed before reserve shown as volume')
                else:
                    self._add_solution_record(coupling, 'DIC', 'coupling reagent', steps, 5.0, 'neat/DMF', 0, step_mmol * 5.0, 'DIC amount for synthesizer coupling preparation')
                    add = 'Oxyma' if 'Oxyma' in chem else 'HOBt'
                    self._add_solution_record(catalyst, add, 'catalyst/additive', steps, 5.0, 'DMF', 0, step_mmol * 5.0, 'solid catalyst/additive for coupling bottle')
                    self._add_solution_record(solvent, 'DMF', 'coupling solvent reservoir', steps, '', '', 0, step_mmol * 10.0, 'DMF used for coupling/cocktail transfer; practical reserve applied')
                self._add_solution_record(solvent, 'DMF', 'AA stock solvent', steps, '', '', 0, 0, 'AA stock solvent volume is listed in AA table')
                self._add_solution_record(solvent, 'DMF', 'wash/deprotection reservoir', steps, '', '', 0, step_mmol * 8.0 * 10.0, 'DMF wash/deprotection reservoir estimate')
                self._add_solution_record(solvent, 'DCM', 'final wash reservoir', steps, '', '', 0, copies * scale * 3.0 * 10.0, 'DCM final wash reservoir estimate')
            seq = str(r.get('Sequence', '') or '')
            if self._sequence_has_nterm_ac(seq):
                self._add_solution_record(modifier, 'Acetic anhydride (Ac2O)', 'N-terminal Ac cap', copies, 3.0, 'neat/DMF', 0, copies * scale * 3.0, '')
        return {'coupling': self._solution_records_to_df(coupling), 'catalyst': self._solution_records_to_df(catalyst), 'solvent': self._solution_records_to_df(solvent), 'modifier': self._solution_records_to_df(modifier)}

    def _project_summary_df(self, rows=None):
        rows = rows if rows is not None else self._project_rows()
        out = []
        for i, r in enumerate(rows, 1):
            out.append({'no': i, 'project': r.get('Project', ''), 'peptide_name': r.get('Peptide name', ''), 'lot_no': r.get('LOT No', ''), 'sequence': r.get('Sequence', ''), 'copies': r.get('Copies', ''), 'scale_mmol': r.get('Scale mmol', ''), 'resin': r.get('Resin', ''), 'chemistry': r.get('Chemistry', '')})
        return pd.DataFrame(out)

    def _build_batch_tab(self):
        fr = ttk.Frame(self.tabs)
        self.tabs.add(fr, text='Batch Manager')
        fr.rowconfigure(2, weight=1)
        fr.columnconfigure(0, weight=1)
        top = ttk.Frame(fr, padding=(4, 3))
        top.grid(row=0, column=0, sticky='ew')
        ttk.Label(top, text='Synthesizer stock/cocktail calculator: automatically uses Project Manager peptide items.').pack(side='left', padx=(2, 12))
        ttk.Button(top, text='Refresh totals', command=self.refresh_batch_workspace_preview).pack(side='left', padx=3)
        ttk.Button(top, text='Export batch calculator', command=self._export_batch_calculator).pack(side='left', padx=3)
        ttk.Button(top, text='Save Session Now', command=self.save_autosave_state).pack(side='left', padx=3)
        defaults = ttk.Labelframe(fr, text='Solution prep defaults', padding=5)
        defaults.grid(row=1, column=0, sticky='ew', padx=4, pady=3)
        self.batch_solution_conc = tk.StringVar(value='0.25')
        self.batch_coupling_eq = tk.StringVar(value='10')
        self.batch_actual_round_ml = tk.StringVar(value='10')
        self.batch_actual_extra_ml = tk.StringVar(value='10')
        self.batch_hbtu_eq = tk.StringVar(value='10')
        self.batch_hbtu_conc = tk.StringVar(value='0.4')
        self.batch_default_scale = tk.StringVar(value='0.2')
        self.batch_default_resin = tk.StringVar(value='Rink Amide AM')
        self.batch_default_loading = tk.StringVar(value='0.8')
        self.batch_hbtu_mw = tk.StringVar(value='379.25')
        self.batch_nmp_density = tk.StringVar(value='1.03')
        fields = [('AA conc M', self.batch_solution_conc), ('AA eq', self.batch_coupling_eq), ('Round-up mL', self.batch_actual_round_ml), ('Extra reserve mL', self.batch_actual_extra_ml), ('HBTU eq', self.batch_hbtu_eq), ('HBTU conc M', self.batch_hbtu_conc)]
        for i, (lab, var) in enumerate(fields):
            ttk.Label(defaults, text=lab).grid(row=0, column=i * 2, sticky='w', padx=(2, 3))
            ttk.Entry(defaults, textvariable=var, width=10).grid(row=0, column=i * 2 + 1, sticky='ew', padx=(0, 8))
            try:
                var.trace_add('write', lambda *_: self.after_idle(self.refresh_batch_workspace_preview))
            except Exception:
                pass
        nb = ttk.Notebook(fr)
        nb.grid(row=2, column=0, sticky='nsew', padx=4, pady=4)

        def tab(title, cols):
            frame = ttk.Frame(nb)
            frame.rowconfigure(0, weight=1)
            frame.columnconfigure(0, weight=1)
            nb.add(frame, text=title)
            return self._tree_in_frame(frame, cols)
        material_cols = ['Category', 'Item', 'Solvent', 'Count', 'Eq', 'Conc_M', 'Calculated_mL', 'Actual_mL', 'MW', 'Density', 'Weight_g', 'Volume_mL', 'Note']
        self.batch_aa_tree = tab('AA + Chemicals', material_cols)
        common = ['item', 'purpose', 'count', 'eq', 'solvent', 'conc_M', 'calculated', 'actual', 'unit', 'MW', 'density', 'weight_g', 'volume_mL', 'note']
        self.batch_coupling_reagent_tree = tab('Coupling reagents', common)
        self.batch_catalyst_tree = tab('Catalyst / additive', common)
        self.batch_solvent_tree = tab('Solvents / reservoirs', common)
        self.batch_project_tree = tab('Project summary', ['no', 'project', 'peptide_name', 'lot_no', 'sequence', 'copies', 'scale_mmol', 'resin', 'chemistry'])
        # One visible material list. batch_workflow.refresh recognizes this shared
        # tree and paints L-AA -> D-AA -> Non-natural AA -> Chemical exactly once.
        self.batch_modifier_tree = self.batch_aa_tree
        self.batch_material_tree = self.batch_aa_tree
        self.batch_hbtu_tree = self.batch_coupling_reagent_tree
        self.batch_cap_tree = self.batch_aa_tree
        self.refresh_batch_workspace_preview()

    def refresh_batch_workspace_preview(self):
        try:
            rows = self._project_rows()
            aa_df = self._aa_calculator_df(rows)
            totals = self._batch_totals(rows)
            self._write_tree(self.batch_aa_tree, aa_df, ['AA', 'count', 'eq', 'solvent', 'conc_M', 'calculated_mL', 'actual_mL', 'MW', 'weight_g', 'note'])
            cols = ['item', 'purpose', 'count', 'eq', 'solvent', 'conc_M', 'calculated', 'actual', 'unit', 'MW', 'density', 'weight_g', 'volume_mL', 'note']
            self._write_tree(self.batch_coupling_reagent_tree, totals['coupling'], cols)
            self._write_tree(self.batch_catalyst_tree, totals['catalyst'], cols)
            self._write_tree(self.batch_solvent_tree, totals['solvent'], cols)
            self._write_tree(self.batch_modifier_tree, totals['modifier'], cols)
            self._write_tree(self.batch_project_tree, self._project_summary_df(rows), ['no', 'project', 'peptide_name', 'lot_no', 'sequence', 'copies', 'scale_mmol', 'resin', 'chemistry'])
        except Exception as e:
            print('Batch refresh warning:', e)

    def _export_batch_calculator(self):
        path = filedialog.asksaveasfilename(defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx')])
        if not path:
            return
        from spps_v4_gui import batch_workflow
        tables = batch_workflow.calculate(self)
        with pd.ExcelWriter(path, engine='openpyxl') as writer:
            tables.get('Summary', pd.DataFrame()).to_excel(writer, index=False, sheet_name='00_PROJECT_SUMMARY')
            tables.get('AA + Chemicals', pd.DataFrame()).to_excel(writer, index=False, sheet_name='01_AA_AND_CHEMICALS')
            tables.get('AA stock', pd.DataFrame()).to_excel(writer, index=False, sheet_name='02_AA_STOCK')
            tables.get('Chemicals', pd.DataFrame()).to_excel(writer, index=False, sheet_name='03_CHEMICALS')
            tables.get('Coupling reagents', pd.DataFrame()).to_excel(writer, index=False, sheet_name='04_COUPLING')
            tables.get('Catalyst/additive', pd.DataFrame()).to_excel(writer, index=False, sheet_name='05_CATALYST')
            tables.get('Base/Deprotection', pd.DataFrame()).to_excel(writer, index=False, sheet_name='06_BASE_DEPRO')
            tables.get('Solvents', pd.DataFrame()).to_excel(writer, index=False, sheet_name='07_SOLVENTS')
        messagebox.showinfo('Export complete', f'Batch calculator saved:\n{path}')

    def _format_display_value(self, value, column=''):
        try:
            if self._is_blank(value):
                return ''
            col = str(column or '').lower()
            text_value = str(value).strip()
            if text_value.lower() in {'manual', 'manual required', 'n/a'}:
                return text_value
            number = self._display_to_float(value)
            if number is None:
                text = text_value
                for bad in ('♪', '♫', '♬', '♩', '♭', '♯'):
                    text = text.replace(bad, '')
                text = re.sub('[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f]', ' ', text)
                return text.strip()
            if col in {'no', 'line', 'step', 'count', 'copies', 'use_count', 'repeat'}:
                return str(int(round(number))) if abs(number - round(number)) < 1e-09 else f'{number:.2f}'
            volume_markers = ['ml', 'volume', 'actual', 'calculated', 'planned_ml', 'calc_ml', 'reservoir']
            unit_markers = ['unit volume']
            if any((m in col for m in volume_markers + unit_markers)):
                if 'g' not in col and 'weight' not in col:
                    return f'{number:.1f}'
            return f'{number:.2f}'
        except Exception:
            return str(value) if value is not None else ''

    def _write_tree(self, tree: ttk.Treeview, df: pd.DataFrame, columns):
        try:
            for item in tree.get_children():
                tree.delete(item)
            existing = list(tree['columns'])
            if list(existing) != list(columns):
                tree.configure(columns=list(columns))
                for col in columns:
                    tree.heading(col, text=col)
                    tree.column(col, width=130, minwidth=60, anchor='w', stretch=True)
            if df is None or df.empty:
                if tree in (getattr(self, 'live_usage_tree', None), getattr(self, 'material_tree', None)):
                    blank = {c: '' for c in columns}
                    if 'material' in blank:
                        blank['material'] = 'No material rows calculated yet'
                    if 'note' in blank:
                        blank['note'] = 'Click Generate / Update Plan; verify sequence, scale, resin, and coupling settings.'
                    tree.insert('', 'end', values=[blank.get(c, '') for c in columns])
                return
            for _, row in df.iterrows():
                vals = [self._format_display_value(row.get(c, ''), c) for c in columns]
                tree.insert('', 'end', values=vals)
        except Exception as e:
            try:
                for item in tree.get_children():
                    tree.delete(item)
                blank = {c: '' for c in columns}
                if 'material' in blank:
                    blank['material'] = 'Material table render warning'
                if 'note' in blank:
                    blank['note'] = str(e)
                tree.insert('', 'end', values=[blank.get(c, '') for c in columns])
            except Exception:
                pass

    def _pm_items_to_batch_rows(self):
        rows = []
        for item in list(getattr(self, 'pm_items', []) or []):
            seq = str(item.get('sequence', '') or '').strip()
            pep = str(item.get('peptide', '') or '').strip()
            if not seq and (not pep):
                continue
            rows.append({'Project': item.get('project', ''), 'Peptide name': item.get('peptide', ''), 'Form': item.get('form', 'linear'), 'Copies': item.get('copies', '1'), 'N-term': 'Ac' if self._sequence_has_nterm_ac(seq) else item.get('n_term', ''), 'Region 1 seq': seq, 'Region 1 eq': '1', 'Linker': item.get('linker', ''), 'Region 2 seq': item.get('region2_seq', ''), 'Region 2 eq': item.get('region2_eq', ''), 'Tag': item.get('tag', ''), 'Label': item.get('label', ''), 'C-term': item.get('c_term', 'NH2'), 'D/non-natural notes': item.get('notes', ''), 'Chemistry': item.get('chemistry', 'DIC/HOBt'), 'Scale mmol': item.get('scale', getattr(self, 'batch_default_scale', const_var('0.2')).get()), 'AA conc M': getattr(self, 'batch_solution_conc', const_var('0.25')).get(), 'AA coupling eq': getattr(self, 'batch_coupling_eq', const_var('10')).get(), 'Resin': item.get('resin', getattr(self, 'batch_default_resin', const_var('Rink Amide AM')).get()), 'Loading': item.get('loading', getattr(self, 'batch_default_loading', const_var('0.8')).get()), 'LOT No': item.get('lot', ''), 'Status': item.get('status', 'Ready')})
        return rows

    def _batch_rows_from_tree(self):
        pm_rows = self._pm_items_to_batch_rows()
        if pm_rows:
            return pm_rows
        rows = []
        if not hasattr(self, 'batch_tree'):
            return rows
        for item in self.batch_tree.get_children():
            vals = list(self.batch_tree.item(item, 'values'))
            vals += [''] * (len(self.batch_columns) - len(vals))
            d = dict(zip(self.batch_columns, vals))
            if not str(d.get('Region 1 seq', '')).strip() and (not str(d.get('Peptide name', '')).strip()):
                continue
            rows.append(d)
        return rows

    def pm_generate_selected(self):
        try:
            self.pm_save_selected()
            idx = self.pm_current_index()
            if idx is None:
                return
            item = self.pm_items[idx]
            self.pm_apply_item_to_single_plan(item)
            self.generate_update_plan()
            item['status'] = 'Calculated'
            self._write_tree(self.pm_selected_plan_tree, self.pm_tree_to_df(self.tree), list(self.pm_selected_plan_tree['columns']))
            self._write_tree(self.pm_selected_material_tree, self.pm_tree_to_df(self.live_usage_tree), list(self.pm_selected_material_tree['columns']))
            try:
                self.pm_selected_check_text.delete('1.0', 'end')
                self.pm_selected_check_text.insert('end', self.short_step_text.get('1.0', 'end'))
            except Exception:
                pass
            self.pm_refresh_list(keep_index=idx, reload_editor=False)
            self.pm_update_summary()
            self.refresh_batch_workspace_preview()
            self.schedule_autosave()
        except Exception as e:
            try:
                item['status'] = 'Error'
            except Exception:
                pass
            messagebox.showerror('Project Manager', str(e))

    def _bind_setup_live_update(self):
        if getattr(self, '_setup_live_bound', False):
            return
        self._setup_live_bound = True
        vars_to_watch = ['coupling_eq', 'coupling_time_h', 'coupling_repeats', 'modifier_eq', 'modifier_repeats', 'solvent_volume_mode', 'amide_ml_per_mmol', 'ctc_ml_per_mmol', 'solvent_molarity_m', 'default_reagent', 'default_reagent_eq', 'default_reagent_count', 'default_catalyst', 'default_catalyst_eq', 'default_catalyst_count', 'default_base', 'default_base_eq', 'default_base_count', 'default_coupling_solution_solvent', 'default_solvent1', 'default_solvent1_count', 'default_solvent2', 'default_solvent2_count', 'default_loading_dissolve_solvent', 'final_meoh_count', 'default_depro', 'default_depro_ratio', 'default_depro_count', 'batch_solution_conc', 'batch_coupling_eq', 'batch_actual_round_ml', 'batch_actual_extra_ml', 'batch_hbtu_eq', 'batch_hbtu_conc', 'batch_hbtu_mw', 'batch_nmp_density']

        def _changed(*_):
            try:
                from spps_v4_gui import batch_workflow
                batch_workflow.invalidate_and_refresh_if_visible(self)
                self.pm_update_summary()
                self.schedule_autosave()
            except Exception:
                pass
        for name in vars_to_watch:
            var = getattr(self, name, None)
            if hasattr(var, 'trace_add'):
                try:
                    var.trace_add('write', lambda *_: self.after_idle(_changed))
                except Exception:
                    pass

    def pm_live_sync_selected(self):
        if (getattr(self, '_pm_loading_editor', False)
                or getattr(self, '_v229_switching', False)
                or getattr(self, '_v2212_switching', False)):
            return
        idx = self.pm_current_index() if hasattr(self, 'pm_list') else None
        if idx is None or idx < 0 or idx >= len(getattr(self, 'pm_items', [])):
            return
        try:
            self.pm_items[idx].update({'project': self.pm_project.get().strip(), 'peptide': self.pm_peptide.get().strip(), 'sequence': self.pm_sequence.get().strip(), 'scale': self.pm_scale.get().strip(), 'resin': self.pm_resin.get().strip(), 'loading': self.pm_loading.get().strip(), 'lot': self.pm_lot.get().strip(), 'chemistry': self.pm_chemistry.get().strip(), 'copies': self.pm_copies.get().strip(), 'status': self.pm_items[idx].get('status', 'Ready')})
            self.pm_refresh_list(keep_index=idx, reload_editor=False)
            self.pm_update_summary()
            from spps_v4_gui import batch_workflow
            batch_workflow.invalidate_and_refresh_if_visible(self)
            self.schedule_autosave()
        except Exception:
            pass

    def _build_pm_setup_panel(self, parent):
        super()._build_pm_setup_panel(parent)
        self._bind_setup_live_update()

    def pm_calculate_all(self):
        return self.pm_generate_selected()

