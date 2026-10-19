// Exports what is on screen (current filters, chart type and table page) to a PDF that keeps the dashboard look.
// The page is rendered to an image (html2canvas) and split into A4 landscape pages at card/section boundaries,
// so no chart is cut in half. Libraries are loaded only when the user clicks the button.

const MARGIN = 18;          // pt
const FOOTER = 16;          // pt reserved for the footer line
const BREAK_SELECTORS = [".top", ".filters", ".active-f", ".tiles", ".sec", ".card", "footer", "table.grid tbody tr"];

function cdmxNow() {
  return new Date().toLocaleString("en-CA", { timeZone: "America/Mexico_City", hour12: false, year: "numeric",
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).replace(",", "");
}

const nextFrame = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));

export async function exportDashboardPdf(root, { filtersLabel = "All data", title = "Portfolio Health Dashboard" } = {}) {
  const [{ default: html2canvas }, { jsPDF }] = await Promise.all([import("html2canvas"), import("jspdf")]);
  const scrollY = window.scrollY;
  root.classList.add("pdf-capture");
  try {
    window.scrollTo(0, 0);
    if (document.fonts?.ready) await document.fonts.ready;
    await nextFrame();
    await new Promise((r) => setTimeout(r, 350));            // let chart animations settle

    const rootTop = root.getBoundingClientRect().top + window.scrollY;
    const topOf = (el) => el.getBoundingClientRect().top + window.scrollY - rootTop;
    // A section heading stays with the cards below it: no break right under a heading
    const headings = [...root.querySelectorAll(".sec")].map((el) => [topOf(el), topOf(el) + el.offsetHeight + 40]);
    const breaks = new Set();
    root.querySelectorAll(BREAK_SELECTORS.join(",")).forEach((el) => {
      const top = topOf(el);
      if (top <= 0 || headings.some(([a, b]) => top > a + 1 && top <= b)) return;
      breaks.add(Math.round(top - 6));                      // break just above the element (keeps its border)
    });

    const scale = Math.min(2, window.devicePixelRatio > 1 ? window.devicePixelRatio : 2);
    const canvas = await html2canvas(root, {
      scale, backgroundColor: getComputedStyle(document.body).backgroundColor || "#f4f6fa", useCORS: true,
      logging: false, windowWidth: document.documentElement.scrollWidth,
      ignoreElements: (el) => el.hasAttribute?.("data-pdf-hide") || el.classList?.contains("drawer-bg"),
    });

    const pdf = new jsPDF({ orientation: "landscape", unit: "pt", format: "a4", compress: true });
    const pw = pdf.internal.pageSize.getWidth();
    const ph = pdf.internal.pageSize.getHeight();
    const contentW = pw - 2 * MARGIN;
    const pxPerPt = canvas.width / contentW;
    const pageH = Math.floor((ph - 2 * MARGIN - FOOTER) * pxPerPt);
    const cuts = [...breaks].map((b) => b * scale).sort((a, b) => a - b);

    const slices = [];
    let y = 0;
    while (y < canvas.height - 2) {
      let end = Math.min(y + pageH, canvas.height);
      if (end < canvas.height) {
        const ok = cuts.filter((c) => c > y + pageH * 0.35 && c <= y + pageH);
        if (ok.length) end = ok[ok.length - 1];
      }
      slices.push([y, end]);
      y = end;
    }

    const stamp = cdmxNow();
    slices.forEach(([y0, y1], i) => {
      if (i > 0) pdf.addPage();
      const part = document.createElement("canvas");
      part.width = canvas.width;
      part.height = y1 - y0;
      const ctx = part.getContext("2d");
      ctx.fillStyle = "#f4f6fa";
      ctx.fillRect(0, 0, part.width, part.height);
      ctx.drawImage(canvas, 0, y0, canvas.width, y1 - y0, 0, 0, canvas.width, y1 - y0);
      pdf.setFillColor(244, 246, 250);
      pdf.rect(0, 0, pw, ph, "F");
      pdf.addImage(part.toDataURL("image/jpeg", 0.92), "JPEG", MARGIN, MARGIN, contentW, (y1 - y0) / pxPerPt);
      pdf.setFontSize(8);
      pdf.setTextColor(91, 100, 117);
      pdf.text(`${title} · ${filtersLabel} · exported ${stamp} (CDMX)`, MARGIN, ph - MARGIN + 4);
      pdf.text(`Page ${i + 1} of ${slices.length}`, pw - MARGIN, ph - MARGIN + 4, { align: "right" });
    });

    pdf.setProperties({ title: `${title} — ${stamp}`, subject: filtersLabel, creator: "Portfolio Health Dashboard" });
    const fname = `portfolio-health-dashboard_${stamp.replace(/[: ]/g, "").replace(/-/g, "")}.pdf`;
    pdf.save(fname);
    return { pages: slices.length, file: fname };
  } finally {
    root.classList.remove("pdf-capture");
    window.scrollTo(0, scrollY);
  }
}
