/* DocBridge's offline KaTeX host. No document content is written to disk. */
window.docbridgeKaTeXReady = typeof katex !== "undefined";
window.renderFormula = async function (source, displayMode, fontSize) {
    const host = document.getElementById("host");
    const formula = document.getElementById("formula");
    host.style.fontSize = fontSize + "px";
    formula.replaceChildren();
    katex.render(source, formula, {
        displayMode, output: "html", throwOnError: true, strict: "ignore",
        maxExpand: 1000, maxSize: 20, macros: {},
        trust: function () { throw new Error("公式图片不支持外部资源或 HTML 扩展命令"); }
    });
    await document.fonts.ready;
    for (const font of document.fonts) {
        if (font.status === "error") throw new Error("KaTeX 字体未能加载");
    }
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const rect = formula.getBoundingClientRect();
    const x = Math.max(0, Math.floor(rect.left - 2));
    const y = Math.max(0, Math.floor(rect.top - 2));
    return {
        x, y, width: Math.ceil(rect.right + 2) - x,
        height: Math.ceil(rect.bottom + 2) - y,
        baseline: document.getElementById("baseline").getBoundingClientRect().top
    };
};
