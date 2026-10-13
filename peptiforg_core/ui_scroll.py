from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class VerticalPageScroller:
    """Stable vertical-only scrolling for long Tk analysis pages.

    The inner frame follows the viewport width. Wheel events are coalesced and
    ignored at the upper/lower boundary so high-resolution mice do not build up
    redundant yview calls. Scrollregion updates are debounced and only committed
    when the geometry actually changes.
    """

    def __init__(self, owner, parent, *, background="#F3F6FA", padding=0, wheel_step=3):
        self.owner = owner
        self.canvas = tk.Canvas(parent, highlightthickness=0, borderwidth=0, background=background, yscrollincrement=24)
        self.scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.inner = ttk.Frame(self.canvas, padding=padding)
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self._region_after = None
        self._wheel_after = None
        self._wheel_accum = 0.0
        self._wheel_step = max(1, int(wheel_step))
        self._last_region = None
        self._wheel_tag = f"PepforgePageWheel_{id(self)}"

        self.inner.bind("<Configure>", self._schedule_region, add="+")
        self.canvas.bind("<Configure>", self._on_canvas_configure, add="+")
        self.canvas.bind_class(self._wheel_tag, "<MouseWheel>", self._on_wheel, add="+")
        self.canvas.bind_class(self._wheel_tag, "<Button-4>", self._on_linux_up, add="+")
        self.canvas.bind_class(self._wheel_tag, "<Button-5>", self._on_linux_down, add="+")
        self.canvas.bind_class(self._wheel_tag, "<Prior>", lambda e: self._page(-1), add="+")
        self.canvas.bind_class(self._wheel_tag, "<Next>", lambda e: self._page(1), add="+")
        self.canvas.bind_class(self._wheel_tag, "<Home>", lambda e: self._moveto(0.0), add="+")
        self.canvas.bind_class(self._wheel_tag, "<End>", lambda e: self._moveto(1.0), add="+")
        self.owner.after_idle(self._install_bindtag_recursive)
        self.owner.after(250, self._install_bindtag_recursive)
        self.owner.after(1000, self._install_bindtag_recursive)

    def grid(self, **kwargs):
        self.canvas.grid(**kwargs)

    def pack(self, **kwargs):
        self.canvas.pack(**kwargs)

    def _install_bindtag_recursive(self):
        try:
            stack=[self.canvas, self.inner]
            seen=set()
            while stack:
                widget=stack.pop()
                key=str(widget)
                if key in seen:
                    continue
                seen.add(key)
                tags=list(widget.bindtags())
                if self._wheel_tag not in tags:
                    # Put page scrolling before widget-class wheel handlers so
                    # combobox/spinbox values do not change while scrolling a page.
                    tags.insert(1, self._wheel_tag)
                    widget.bindtags(tuple(tags))
                try:
                    stack.extend(widget.winfo_children())
                except tk.TclError:
                    pass
        except tk.TclError:
            return

    def _on_canvas_configure(self, event):
        try:
            width=max(1, int(event.width))
            if int(float(self.canvas.itemcget(self.window, "width") or 0)) != width:
                self.canvas.itemconfigure(self.window, width=width)
        except (tk.TclError, ValueError):
            return
        self._schedule_region()

    def _schedule_region(self, _event=None):
        if self._region_after is not None:
            try:
                self.owner.after_cancel(self._region_after)
            except tk.TclError:
                pass
        # A short debounce prevents dozens of bbox recalculations while the
        # scrollbar thumb is dragged or a large section is being populated.
        self._region_after=self.owner.after(35, self._commit_region)

    def _commit_region(self):
        self._region_after=None
        try:
            bbox=self.canvas.bbox("all")
            if bbox and bbox != self._last_region:
                self.canvas.configure(scrollregion=bbox)
                self._last_region=bbox
        except tk.TclError:
            pass

    def _at_edge(self, direction):
        try:
            lo, hi = self.canvas.yview()
            return (direction < 0 and lo <= 1e-6) or (direction > 0 and hi >= 1.0 - 1e-6)
        except tk.TclError:
            return True

    def _queue_units(self, units):
        direction = 1 if units > 0 else -1
        if self._at_edge(direction):
            self._wheel_accum = 0.0
            return "break"
        self._wheel_accum += units
        if self._wheel_after is None:
            self._wheel_after=self.owner.after(12, self._flush_wheel)
        return "break"

    def _flush_wheel(self):
        self._wheel_after=None
        units=int(round(self._wheel_accum))
        self._wheel_accum=0.0
        if not units:
            return
        direction=1 if units > 0 else -1
        if self._at_edge(direction):
            return
        try:
            self.canvas.yview_scroll(units, "units")
        except tk.TclError:
            pass

    def _on_wheel(self, event):
        delta=getattr(event, "delta", 0) or 0
        if not delta:
            return "break"
        # Windows usually reports +/-120; high-resolution mice may report
        # smaller values. Normalize without amplifying large bursts.
        amount = -delta / 120.0
        amount = max(-self._wheel_step, min(self._wheel_step, amount))
        return self._queue_units(amount * self._wheel_step)

    def _on_linux_up(self, _event):
        return self._queue_units(-self._wheel_step)

    def _on_linux_down(self, _event):
        return self._queue_units(self._wheel_step)

    def _page(self, direction):
        if self._at_edge(direction):
            return "break"
        try:
            self.canvas.yview_scroll(direction, "pages")
        except tk.TclError:
            pass
        return "break"

    def _moveto(self, fraction):
        try:
            self.canvas.yview_moveto(float(fraction))
        except tk.TclError:
            pass
        return "break"
