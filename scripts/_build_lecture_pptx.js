/* 智衍 EvolvIQ · 系统介绍 PPT（上海铁路通信有限公司专场）
 * 对齐 docs/EXTERNAL_NARRATIVE.md 对外口径；纯 pptxgenjs 原生图形，无原生依赖。
 */
const pptxgen = require("pptxgenjs");
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.author = "杜玉河 · 工业5点0产业生态联盟";
pres.title = "智衍 EvolvIQ 工业智能体平台 · 系统介绍";

const W = 13.33, H = 7.5;
const C = {
  dark: "0B2545", navy: "13315C", steel: "1C4E80",
  teal: "2EC4B6", tealD: "179189", amber: "FF9F1C",
  light: "F4F7FB", card: "FFFFFF", text: "1A2433",
  muted: "64748B", line: "D8E2EC", ice: "CFE3F2", white: "FFFFFF",
};
const FH = "Microsoft YaHei", FB = "Microsoft YaHei";

const shadow = () => ({ type: "outer", color: "1A2433", blur: 7, offset: 3, angle: 135, opacity: 0.16 });
const softShadow = () => ({ type: "outer", color: "1A2433", blur: 5, offset: 2, angle: 135, opacity: 0.10 });

function bg(slide, color) { slide.background = { color }; }

function header(slide, kicker, title) {
  slide.addShape(pres.shapes.RECTANGLE, { x: 0.55, y: 0.55, w: 0.14, h: 0.62, fill: { color: C.teal } });
  slide.addText(kicker, { x: 0.82, y: 0.5, w: 11.5, h: 0.3, fontFace: FB, fontSize: 12, color: C.tealD, bold: true, charSpacing: 2, margin: 0 });
  slide.addText(title, { x: 0.82, y: 0.78, w: 11.8, h: 0.55, fontFace: FH, fontSize: 26, color: C.navy, bold: true, margin: 0 });
}

function footer(slide, n) {
  slide.addShape(pres.shapes.LINE, { x: 0.55, y: 7.02, w: 12.23, h: 0, line: { color: C.line, width: 1 } });
  slide.addText("智衍 EvolvIQ · 工业智能体平台", { x: 0.55, y: 7.06, w: 8, h: 0.3, fontFace: FB, fontSize: 9, color: C.muted, margin: 0 });
  slide.addText(String(n).padStart(2, "0"), { x: 12.0, y: 7.06, w: 0.78, h: 0.3, fontFace: "Arial", fontSize: 9, color: C.muted, align: "right", margin: 0 });
}

function card(slide, x, y, w, h, fill, opts = {}) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.08,
    fill: { color: fill || C.card },
    line: opts.line ? { color: opts.line, width: 1 } : { color: C.line, width: 1 },
    shadow: opts.shadow === false ? undefined : softShadow(),
  });
}

// ============ SLIDE 1 — COVER ============
(function () {
  const s = pres.addSlide(); bg(s, C.dark);
  // decorative concentric motif (right)
  s.addShape(pres.shapes.OVAL, { x: 9.4, y: 1.6, w: 4.6, h: 4.6, fill: { color: C.dark }, line: { color: C.steel, width: 1.5 } });
  s.addShape(pres.shapes.OVAL, { x: 10.3, y: 2.5, w: 2.8, h: 2.8, fill: { color: C.dark }, line: { color: C.teal, width: 1.5 } });
  s.addShape(pres.shapes.OVAL, { x: 11.15, y: 3.35, w: 1.1, h: 1.1, fill: { color: C.teal } });
  for (const a of [0.4, 1.9, 3.4, 4.9]) {
    const cx = 11.7 + 2.2 * Math.cos(a), cy = 3.9 + 2.2 * Math.sin(a);
    s.addShape(pres.shapes.OVAL, { x: cx - 0.09, y: cy - 0.09, w: 0.18, h: 0.18, fill: { color: C.ice } });
  }
  s.addText("智衍 EvolvIQ · 工业智能体平台", { x: 0.8, y: 1.5, w: 8.2, h: 0.4, fontFace: FB, fontSize: 15, color: C.teal, bold: true, charSpacing: 2, margin: 0 });
  s.addText([
    { text: "工业智能体平台", options: { breakLine: true, color: C.white, bold: true } },
    { text: "系统介绍", options: { color: C.white, bold: true } },
  ], { x: 0.8, y: 2.1, w: 8.2, h: 1.8, fontFace: FH, fontSize: 46, lineSpacingMultiple: 1.05, margin: 0 });
  s.addText("为经营管控者与一线执行者，叠加一个「实时决策脑 + 全息真相源」", { x: 0.82, y: 4.05, w: 8.0, h: 0.5, fontFace: FB, fontSize: 16, color: C.ice, margin: 0 });
  // divider
  s.addShape(pres.shapes.RECTANGLE, { x: 0.82, y: 4.9, w: 2.2, h: 0.05, fill: { color: C.teal } });
  s.addText([
    { text: "上海铁路通信有限公司 · 专场交流", options: { breakLine: true, color: C.white, bold: true, fontSize: 16 } },
    { text: "杜玉河 · 工业5点0产业生态联盟", options: { breakLine: true, color: C.ice, fontSize: 12 } },
    { text: "2026.08.05", options: { color: C.ice, fontSize: 12 } },
  ], { x: 0.82, y: 5.1, w: 8.0, h: 1.2, fontFace: FB, lineSpacingMultiple: 1.3, margin: 0 });
})();

// ============ SLIDE 2 — 开场三问 ============
(function () {
  const s = pres.addSlide(); bg(s, C.light);
  header(s, "OPENING · 制造业正在经历什么", "三道分水岭：数据能存，不等于能决策");
  const qs = [
    ["01", "您的 MES / ERP 上了多久？", "大多 3–5 年。但系统里的数据，能实时指导今天的决策吗？"],
    ["02", "现在数据能实时指导决策吗？", "通常不能——经营看板滞后 24 小时+，决策仍靠人肉拉数、凭经验拍板。"],
    ["03", "老师傅的经验被系统化了吗？", "通常没有。人一走，工艺诀窍、排故经验就随之流失。"],
  ];
  let y = 1.7;
  qs.forEach(([n, t, d]) => {
    card(s, 0.55, y, 7.4, 1.45);
    s.addShape(pres.shapes.OVAL, { x: 0.8, y: y + 0.42, w: 0.62, h: 0.62, fill: { color: C.navy } });
    s.addText(n, { x: 0.8, y: y + 0.42, w: 0.62, h: 0.62, align: "center", valign: "middle", fontFace: "Arial", fontSize: 18, bold: true, color: C.white, margin: 0 });
    s.addText(t, { x: 1.65, y: y + 0.22, w: 6.1, h: 0.5, fontFace: FH, fontSize: 16, bold: true, color: C.navy, margin: 0 });
    s.addText(d, { x: 1.65, y: y + 0.72, w: 6.1, h: 0.6, fontFace: FB, fontSize: 12.5, color: C.muted, margin: 0 });
    y += 1.62;
  });
  // right quote
  card(s, 8.2, 1.7, 4.6, 4.55, C.navy);
  s.addShape(pres.shapes.RECTANGLE, { x: 8.2, y: 1.7, w: 0.13, h: 4.55, fill: { color: C.teal } });
  s.addText("核心判断", { x: 8.55, y: 2.0, w: 4.0, h: 0.35, fontFace: FB, fontSize: 13, bold: true, color: C.teal, charSpacing: 2, margin: 0 });
  s.addText([
    { text: "数据能存 ", options: { color: C.white, bold: true } },
    { text: "≠ ", options: { color: C.amber, bold: true } },
    { text: "数据能流；", options: { color: C.white, bold: true, breakLine: true } },
    { text: "数据能看 ", options: { color: C.white, bold: true } },
    { text: "≠ ", options: { color: C.amber, bold: true } },
    { text: "数据能决策。", options: { color: C.white, bold: true } },
  ], { x: 8.55, y: 2.5, w: 4.0, h: 1.1, fontFace: FH, fontSize: 21, lineSpacingMultiple: 1.15, margin: 0 });
  s.addText("AI 智能体时代，核心命题从「怎么存数据」变成了「怎么让数据自己决策」。", { x: 8.55, y: 4.0, w: 4.0, h: 1.0, fontFace: FB, fontSize: 14, color: C.ice, lineSpacingMultiple: 1.3, margin: 0 });
  s.addText("—— 智衍 EvolvIQ 想解决的，正是这一跳。", { x: 8.55, y: 5.3, w: 4.0, h: 0.6, fontFace: FB, fontSize: 12.5, italic: true, color: C.teal, margin: 0 });
  footer(s, 2);
})();

// ============ SLIDE 3 — 一句话定位 ============
(function () {
  const s = pres.addSlide(); bg(s, C.light);
  header(s, "POSITIONING · 我们是什么", "一句话定位：工业智能体平台，而非又一个 AI 工具箱");
  // formula flow
  const steps = [
    ["工业智能体平台", C.navy],
    ["智能分身 / 决策孪生", C.steel],
    ["叠加而非替换", C.tealD],
    ["实时决策", C.teal],
  ];
  let x = 0.55; const fw = 2.85, fgap = 0.42, fy = 1.75, fh = 1.0;
  steps.forEach(([t, col], i) => {
    card(s, x, fy, fw, fh, col);
    s.addText(t, { x: x, y: fy, w: fw, h: fh, align: "center", valign: "middle", fontFace: FH, fontSize: 15, bold: true, color: C.white, margin: 0 });
    if (i < steps.length - 1) {
      const ax = x + fw + 0.04;
      s.addShape(pres.shapes.LINE, { x: ax, y: fy + fh / 2, w: fgap - 0.08, h: 0, line: { color: C.muted, width: 2, endArrowType: "triangle" } });
    }
    x += fw + fgap;
  });
  // route A explanation
  card(s, 0.55, 3.1, 12.23, 1.5, C.card);
  s.addShape(pres.shapes.RECTANGLE, { x: 0.55, y: 3.1, w: 0.13, h: 1.5, fill: { color: C.amber } });
  s.addText("路线 A：不推倒你已有的系统", { x: 0.9, y: 3.25, w: 11.5, h: 0.4, fontFace: FH, fontSize: 16, bold: true, color: C.navy, margin: 0 });
  s.addText("在其上叠加一个「实时决策脑 + 全息真相源」。ERP / MES 退居执行回写与审计，智能分身负责把散落各处的实时数据，凝练成可执行的经营判断。不替换、不重来、不绑定。", { x: 0.9, y: 3.7, w: 11.6, h: 0.8, fontFace: FB, fontSize: 13.5, color: C.text, lineSpacingMultiple: 1.25, margin: 0 });
  // two takeaways
  const tk = [
    ["叠加，不是推倒", "已有信息化资产继续发光，新增的是「决策层」能力。"],
    ["人留终审", "分身是经营管控者 / 执行者的「增强」，不是「替身」——凡涉责任，人拍板。"],
  ];
  let ty = 4.95;
  tk.forEach(([t, d]) => {
    card(s, 0.55, ty, 6.0, 1.55, C.card);
    s.addShape(pres.shapes.OVAL, { x: 0.8, y: ty + 0.3, w: 0.5, h: 0.5, fill: { color: C.teal } });
    s.addText("✓", { x: 0.8, y: ty + 0.3, w: 0.5, h: 0.5, align: "center", valign: "middle", fontFace: "Arial", fontSize: 16, bold: true, color: C.white, margin: 0 });
    s.addText(t, { x: 1.45, y: ty + 0.22, w: 4.9, h: 0.45, fontFace: FH, fontSize: 15, bold: true, color: C.navy, margin: 0 });
    s.addText(d, { x: 1.45, y: ty + 0.68, w: 4.9, h: 0.75, fontFace: FB, fontSize: 12, color: C.muted, lineSpacingMultiple: 1.2, margin: 0 });
    ty += 0; // reset for second
  });
  // second card manually placed
  card(s, 6.78, 4.95, 6.0, 1.55, C.card);
  s.addShape(pres.shapes.OVAL, { x: 7.03, y: 5.25, w: 0.5, h: 0.5, fill: { color: C.teal } });
  s.addText("✓", { x: 7.03, y: 5.25, w: 0.5, h: 0.5, align: "center", valign: "middle", fontFace: "Arial", fontSize: 16, bold: true, color: C.white, margin: 0 });
  s.addText(tk[1][0], { x: 7.68, y: 5.17, w: 4.9, h: 0.45, fontFace: FH, fontSize: 15, bold: true, color: C.navy, margin: 0 });
  s.addText(tk[1][1], { x: 7.68, y: 5.63, w: 4.9, h: 0.75, fontFace: FB, fontSize: 12, color: C.muted, lineSpacingMultiple: 1.2, margin: 0 });
  card(s, 0.55, 4.95, 6.0, 1.55, C.card);
  s.addShape(pres.shapes.OVAL, { x: 0.8, y: 5.25, w: 0.5, h: 0.5, fill: { color: C.teal } });
  s.addText("✓", { x: 0.8, y: 5.25, w: 0.5, h: 0.5, align: "center", valign: "middle", fontFace: "Arial", fontSize: 16, bold: true, color: C.white, margin: 0 });
  s.addText(tk[0][0], { x: 1.45, y: 5.17, w: 4.9, h: 0.45, fontFace: FH, fontSize: 15, bold: true, color: C.navy, margin: 0 });
  s.addText(tk[0][1], { x: 1.45, y: 5.63, w: 4.9, h: 0.75, fontFace: FB, fontSize: 12, color: C.muted, lineSpacingMultiple: 1.2, margin: 0 });
  footer(s, 3);
})();

// ============ SLIDE 4 — 什么是智能分身 ============
(function () {
  const s = pres.addSlide(); bg(s, C.light);
  header(s, "CONCEPT · 决策孪生", "智能分身（决策孪生）：不是聊天机器人，是会干活的智能体");
  // top: comparison two cards (non-overlapping with loop below)
  const cols = [
    ["传统软件 / 大模型问答", C.muted, ["你告诉它「怎么做」（编程）", "可能编造数字、给通用建议", "无记忆、无工具、无执行", "问→答，止步于信息"]],
    ["智衍 智能分身", C.tealD, ["你告诉它「要什么」（目标）", "实时调取系统真数据", "有记忆 · 有知识图谱 · 有工具", "感知→认知→决策→执行→校验"]],
  ];
  let cx = 0.55;
  cols.forEach(([t, col, items]) => {
    card(s, cx, 1.6, 5.7, 2.2, C.card);
    s.addShape(pres.shapes.RECTANGLE, { x: cx, y: 1.6, w: 5.7, h: 0.55, fill: { color: col } });
    s.addText(t, { x: cx, y: 1.6, w: 5.7, h: 0.55, align: "center", valign: "middle", fontFace: FH, fontSize: 15, bold: true, color: C.white, margin: 0 });
    s.addText(items.map((it) => ({ text: it, options: { bullet: { code: "2022" }, breakLine: true, color: C.text } })),
      { x: cx + 0.35, y: 2.28, w: 5.0, h: 1.4, fontFace: FB, fontSize: 12.5, lineSpacingMultiple: 1.22, paraSpaceAfter: 4, margin: 0 });
    cx += 6.05;
  });
  // bottom: 5-step loop (centered horizontal flow + return arrow), clearly below cards
  s.addText("一个分身的运转闭环", { x: 0.55, y: 3.95, w: 6.0, h: 0.4, fontFace: FH, fontSize: 15, bold: true, color: C.navy, align: "left", margin: 0 });
  const steps = ["感知", "认知", "决策", "执行", "自我进化"];
  const nw = 1.18, ngap = 0.22, ny = 4.42, nh = 0.82;
  const totalW = 5 * nw + 4 * ngap;
  const startX = (13.33 - totalW) / 2;
  steps.forEach((st, i) => {
    const x = startX + i * (nw + ngap);
    card(s, x, ny, nw, nh, i === 4 ? C.amber : C.steel, { line: i === 4 ? C.amber : C.steel });
    s.addText(st, { x, y: ny, w: nw, h: nh, align: "center", valign: "middle", fontFace: FH, fontSize: 13, bold: true, color: C.white, margin: 0 });
    if (i < 4) {
      s.addShape(pres.shapes.LINE, { x: x + nw + 0.03, y: ny + nh / 2, w: ngap - 0.06, h: 0, line: { color: C.muted, width: 2, endArrowType: "triangle" } });
    }
  });
  // return arrow (below), points left from step5 back to step1
  s.addShape(pres.shapes.LINE, { x: startX + 0.5, y: ny + nh + 0.34, w: totalW - 1.0, h: 0, line: { color: C.amber, width: 2.5, beginArrowType: "triangle" } });
  s.addText("自我进化：执行结果回灌认知，下一轮判断更准", { x: startX, y: ny + nh + 0.48, w: totalW, h: 0.38, fontFace: FB, fontSize: 12, italic: true, color: C.tealD, align: "center", margin: 0 });
  // bottom note
  card(s, 0.55, 6.15, 12.23, 0.72, C.navy);
  s.addText([
    { text: "关键定位：分身是「增强」，不是「替身」。", options: { bold: true, color: C.teal } },
    { text: " 凡涉及对外责任与重大判断，始终「人留终审」——系统给预案，人拍板。", options: { color: C.ice } },
  ], { x: 0.85, y: 6.15, w: 11.7, h: 0.72, valign: "middle", fontFace: FB, fontSize: 12.5, margin: 0 });
  footer(s, 4);
})();

// ============ SLIDE 5 — 四层框架 ============
(function () {
  const s = pres.addSlide(); bg(s, C.light);
  header(s, "FRAMEWORK · 四层分身", "四层分身框架：从产业走势，钻到一条产线的换线预案");
  const layers = [
    ["产业级", "产业决策分身", "全球价值链 · 宏观走势", "外圈（零集成 · 免费）", C.navy],
    ["行业级", "行业洞察分身", "同行对标 · 标杆参照", "外圈（声明式现状）", C.steel],
    ["企业级", "经营管控分身", "经营驾驶舱 · 跨域决策", "中圈（接入客户数据）", C.tealD],
    ["专业级", "岗位执行分身", "设备 · 工艺 · 工序", "内圈（私有化深度集成）", C.teal],
  ];
  let y = 1.7;
  layers.forEach(([lv, nm, sol, ring, col]) => {
    card(s, 0.55, y, 9.0, 1.12, C.card);
    s.addShape(pres.shapes.RECTANGLE, { x: 0.55, y: y, w: 1.7, h: 1.12, fill: { color: col } });
    s.addText(lv, { x: 0.55, y: y, w: 1.7, h: 1.12, align: "center", valign: "middle", fontFace: FH, fontSize: 17, bold: true, color: C.white, margin: 0 });
    s.addText(nm, { x: 2.4, y: y + 0.16, w: 7.0, h: 0.45, fontFace: FH, fontSize: 16, bold: true, color: C.navy, margin: 0 });
    s.addText([
      { text: "解决：", options: { color: C.tealD, bold: true } },
      { text: sol + "    ", options: { color: C.text } },
      { text: "对应：", options: { color: C.tealD, bold: true } },
      { text: ring, options: { color: C.muted } },
    ], { x: 2.4, y: y + 0.62, w: 7.0, h: 0.4, fontFace: FB, fontSize: 12, margin: 0 });
    y += 1.24;
  });
  // right moat card
  card(s, 9.75, 1.7, 3.03, 4.85, C.navy);
  s.addShape(pres.shapes.RECTANGLE, { x: 9.75, y: 1.7, w: 0.13, h: 4.85, fill: { color: C.teal } });
  s.addText("护城河", { x: 10.0, y: 1.95, w: 2.7, h: 0.4, fontFace: FH, fontSize: 16, bold: true, color: C.teal, margin: 0 });
  s.addText("四层贯通「同一套知识资产」", { x: 10.0, y: 2.45, w: 2.65, h: 0.7, fontFace: FH, fontSize: 14, bold: true, color: C.white, lineSpacingMultiple: 1.2, margin: 0 });
  s.addText("Agent 可跨层下钻——从一颗器件的全球供需，一路钻到一条产线的换线预案。", { x: 10.0, y: 3.2, w: 2.65, h: 1.2, fontFace: FB, fontSize: 12.5, color: C.ice, lineSpacingMultiple: 1.3, margin: 0 });
  s.addText("这是「平台」而非「单点工具」的根本差异。", { x: 10.0, y: 5.4, w: 2.65, h: 1.2, fontFace: FB, fontSize: 12.5, italic: true, color: C.teal, lineSpacingMultiple: 1.3, margin: 0 });
  footer(s, 5);
})();

// ============ SLIDE 6 — 总体架构 ============
(function () {
  const s = pres.addSlide(); bg(s, C.light);
  header(s, "ARCHITECTURE · 总体架构", "平台总纲：一脊 · 一体 · 四体系 · 一底座 · 五环节");
  // Band A: 物理存在脊
  s.addText("物理存在脊（5 级）", { x: 0.55, y: 1.62, w: 3, h: 0.3, fontFace: FB, fontSize: 11, bold: true, color: C.tealD, margin: 0 });
  const spine = ["行业", "产业", "企业", "岗位", "对象"];
  let sx = 0.55; const sw = 2.35, sgap = 0.13;
  spine.forEach((t, i) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: sx, y: 1.95, w: sw, h: 0.55, rectRadius: 0.06, fill: { color: C.navy }, shadow: softShadow() });
    s.addText(t, { x: sx, y: 1.95, w: sw, h: 0.55, align: "center", valign: "middle", fontFace: FH, fontSize: 13, bold: true, color: C.white, margin: 0 });
    sx += sw + sgap;
  });
  // Band B: 数字孪生载体
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.55, y: 2.7, w: 12.23, h: 0.5, rectRadius: 0.06, fill: { color: C.steel } });
  s.addText("数字孪生载体（一体）：持久对象，记忆 · 技能 · 知识图谱 · 行动 皆附其上", { x: 0.55, y: 2.7, w: 12.23, h: 0.5, align: "center", valign: "middle", fontFace: FH, fontSize: 13, bold: true, color: C.white, margin: 0 });
  // Band C: 四体系
  s.addText("四体系（每个节点都有）", { x: 0.55, y: 3.35, w: 4, h: 0.3, fontFace: FB, fontSize: 11, bold: true, color: C.tealD, margin: 0 });
  const sys = [["记忆体系", "学到什么"], ["技能体系", "能做什么"], ["知识图谱体系", "知道什么关系"], ["行动体系（手与脚）", "把认知变动作"]];
  let cx2 = 0.55; const cw = 2.95, cgap = 0.13;
  sys.forEach(([t, d]) => {
    card(s, cx2, 3.7, cw, 1.15);
    s.addText(t, { x: cx2 + 0.15, y: 3.82, w: cw - 0.3, h: 0.45, fontFace: FH, fontSize: 13.5, bold: true, color: C.navy, margin: 0 });
    s.addText(d, { x: cx2 + 0.15, y: 4.28, w: cw - 0.3, h: 0.45, fontFace: FB, fontSize: 11.5, color: C.muted, margin: 0 });
    cx2 += cw + cgap;
  });
  // Band D: 五环节闭环
  s.addText("五环节闭环（动态运转流）", { x: 0.55, y: 5.05, w: 4, h: 0.3, fontFace: FB, fontSize: 11, bold: true, color: C.tealD, margin: 0 });
  const loop = ["感知", "认知", "决策", "执行", "自我进化"];
  let lx = 0.55; const lw = 2.35, lgap = 0.13;
  loop.forEach((t, i) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: lx, y: 5.4, w: lw, h: 0.62, rectRadius: 0.06, fill: { color: i === 4 ? C.amber : C.tealD }, shadow: softShadow() });
    s.addText(t, { x: lx, y: 5.4, w: lw, h: 0.62, align: "center", valign: "middle", fontFace: FH, fontSize: 13, bold: true, color: C.white, margin: 0 });
    if (i < 4) s.addShape(pres.shapes.LINE, { x: lx + lw + 0.01, y: 5.71, w: lgap - 0.02, h: 0, line: { color: C.muted, width: 2, endArrowType: "triangle" } });
    lx += lw + lgap;
  });
  // Band E: 治理底座
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.55, y: 6.25, w: 12.23, h: 0.5, rectRadius: 0.06, fill: { color: C.dark } });
  s.addText("治理底座（一底座）：合规闸门 · 回写审计 · 权限三层 · 匿名铁律 · 凭证隔离 · 租户单一真相源", { x: 0.55, y: 6.25, w: 12.23, h: 0.5, align: "center", valign: "middle", fontFace: FH, fontSize: 12.5, bold: true, color: C.ice, margin: 0 });
  footer(s, 6);
})();

// ============ SLIDE 7 — 六路感知 ============
(function () {
  const s = pres.addSlide(); bg(s, C.light);
  header(s, "PERCEPTION · 六路感知", "六路感知：把碎片信号汇成「全息真相源」");
  const ch = [
    ["网关", "设备 / 产线", "贴片机状态、回流焊温度曲线"],
    ["系统", "ERP / MES / WMS", "工单、报工、库存"],
    ["人员", "人 / 群", "车间主任群里的「料可能不够」"],
    ["行业", "行业 / 供应链", "芯片产能、供应商动态"],
    ["会议", "会议 / 协同", "晨会纪要里的决策理由"],
    ["环境", "环境（第⑥路）", "政策 / 市场 / 标杆 / 披露 / 舆情"],
  ];
  // left 3
  let y = 1.75;
  ch.slice(0, 3).forEach(([k, t, d]) => {
    card(s, 0.55, y, 5.3, 1.25);
    s.addShape(pres.shapes.OVAL, { x: 0.8, y: y + 0.35, w: 0.7, h: 0.55, fill: { color: C.navy } });
    s.addText(k, { x: 0.8, y: y + 0.35, w: 0.7, h: 0.55, align: "center", valign: "middle", fontFace: FH, fontSize: 12, bold: true, color: C.white, margin: 0 });
    s.addText(t, { x: 1.65, y: y + 0.18, w: 4.1, h: 0.4, fontFace: FH, fontSize: 14, bold: true, color: C.navy, margin: 0 });
    s.addText(d, { x: 1.65, y: y + 0.6, w: 4.1, h: 0.5, fontFace: FB, fontSize: 11.5, color: C.muted, margin: 0 });
    y += 1.4;
  });
  // right 3
  y = 1.75;
  ch.slice(3).forEach(([k, t, d]) => {
    card(s, 7.45, y, 5.3, 1.25);
    s.addShape(pres.shapes.OVAL, { x: 7.7, y: y + 0.35, w: 0.7, h: 0.55, fill: { color: C.teal } });
    s.addText(k, { x: 7.7, y: y + 0.35, w: 0.7, h: 0.55, align: "center", valign: "middle", fontFace: FH, fontSize: 12, bold: true, color: C.white, margin: 0 });
    s.addText(t, { x: 8.55, y: y + 0.18, w: 4.1, h: 0.4, fontFace: FH, fontSize: 14, bold: true, color: C.navy, margin: 0 });
    s.addText(d, { x: 8.55, y: y + 0.6, w: 4.1, h: 0.5, fontFace: FB, fontSize: 11.5, color: C.muted, margin: 0 });
    y += 1.4;
  });
  // center hub
  s.addShape(pres.shapes.OVAL, { x: 6.0, y: 3.5, w: 1.15, h: 1.15, fill: { color: C.navy }, shadow: shadow() });
  s.addText([{ text: "UNS", options: { breakLine: true, fontSize: 14, bold: true } }, { text: "命名空间", options: { fontSize: 10 } }], { x: 6.0, y: 3.5, w: 1.15, h: 1.15, align: "center", valign: "middle", fontFace: FH, color: C.white, margin: 0 });
  s.addText("第⑥路让外部信息免费且清晰——决策重心回到内部。", { x: 0.55, y: 6.25, w: 12.23, h: 0.5, align: "center", fontFace: FB, fontSize: 12.5, italic: true, color: C.tealD, margin: 0 });
  footer(s, 7);
})();

// ============ SLIDE 8 — 三主义 ============
(function () {
  const s = pres.addSlide(); bg(s, C.light);
  header(s, "METHODOLOGY · 三主义合一", "三主义合一：单一范式解决不了工业问题");
  const three = [
    ["连接主义", "信号感知", "六路把碎片化、隐性信号，用一种语言收进来。", C.navy],
    ["符号主义", "知识锚定", "隐性信号 → 结构化知识（知识图谱）→ 审批门 → 写入图谱。", C.steel],
    ["行为主义", "后果校验", "执行 → 看后果 → 修正知识 → 下次更好。蓝弧闭环。", C.tealD],
  ];
  let x = 0.55; const cw = 3.95, cgap = 0.19;
  three.forEach(([nm, sub, d, col]) => {
    card(s, x, 1.75, cw, 2.5);
    s.addShape(pres.shapes.RECTANGLE, { x: x, y: 1.75, w: cw, h: 0.7, fill: { color: col } });
    s.addText(nm, { x: x, y: 1.75, w: cw, h: 0.7, align: "center", valign: "middle", fontFace: FH, fontSize: 17, bold: true, color: C.white, margin: 0 });
    s.addText(sub, { x: x, y: 2.55, w: cw, h: 0.4, align: "center", fontFace: FH, fontSize: 13, bold: true, color: C.tealD, margin: 0 });
    s.addText(d, { x: x + 0.25, y: 3.0, w: cw - 0.5, h: 1.1, fontFace: FB, fontSize: 12.5, color: C.text, lineSpacingMultiple: 1.3, margin: 0 });
    x += cw + cgap;
  });
  // center cycle (clean horizontal row + bottom return arrow, no crossing)
  s.addText("三主义的活循环", { x: 0.55, y: 4.45, w: 12.23, h: 0.4, align: "center", fontFace: FH, fontSize: 15, bold: true, color: C.navy, margin: 0 });
  const cyc = [["连接", 1.5], ["符号", 5.15], ["行为", 8.8]];
  cyc.forEach(([t, cx3]) => {
    s.addShape(pres.shapes.OVAL, { x: cx3, y: 4.9, w: 1.4, h: 1.4, fill: { color: C.teal }, shadow: softShadow() });
    s.addText(t, { x: cx3, y: 4.9, w: 1.4, h: 1.4, align: "center", valign: "middle", fontFace: FH, fontSize: 15, bold: true, color: C.white, margin: 0 });
  });
  s.addShape(pres.shapes.LINE, { x: 2.9, y: 5.6, w: 2.25, h: 0, line: { color: C.amber, width: 2.5, endArrowType: "triangle" } });
  s.addShape(pres.shapes.LINE, { x: 6.55, y: 5.6, w: 2.25, h: 0, line: { color: C.amber, width: 2.5, endArrowType: "triangle" } });
  s.addShape(pres.shapes.LINE, { x: 2.2, y: 6.45, w: 8.0, h: 0, line: { color: C.amber, width: 2.5, beginArrowType: "triangle" } });
  s.addText("隐性信号（连接）→ 知识锚定（符号）→ 执行 → 结果反馈（行为）→ 经验沉淀", { x: 0.55, y: 6.62, w: 12.23, h: 0.38, align: "center", fontFace: FB, fontSize: 12, italic: true, color: C.muted, margin: 0 });
  footer(s, 8);
})();

// ============ SLIDE 9 — 25 智能分身矩阵 ============
(function () {
  const s = pres.addSlide(); bg(s, C.light);
  header(s, "AGENTS · 25 个智能分身", "25 个智能分身：覆盖产线 · 管理 · 供应链（高亮为铁路通信最相关）");
  const groups = [
    ["产线层", C.navy, ["smt_changeover", "aoi_judge", "oee_optimizer", "pm_maintenance", "quality_trace", "dfm_check", "eco_change"], ["smt_changeover", "pm_maintenance", "quality_trace"]],
    ["管理层", C.steel, ["aps_scheduler", "cost_analysis", "energy_carbon", "executive_cockpit", "compliance_q", "ipc_standard"], ["executive_cockpit", "ipc_standard"]],
    ["供应链层", C.tealD, ["supply_chain", "wms_logistics", "demand_order", "procurement_manage", "rd_npi", "bom_selector", "tacit_capture"], ["supply_chain", "tacit_capture"]],
  ];
  let x = 0.55; const gw = 4.04, ggap = 0.06;
  groups.forEach(([gt, col, agents, hot]) => {
    card(s, x, 1.7, gw, 4.9);
    s.addShape(pres.shapes.RECTANGLE, { x: x, y: 1.7, w: gw, h: 0.6, fill: { color: col } });
    s.addText(gt, { x: x, y: 1.7, w: gw, h: 0.6, align: "center", valign: "middle", fontFace: FH, fontSize: 16, bold: true, color: C.white, margin: 0 });
    let ay = 2.5;
    agents.forEach((a) => {
      const isHot = hot.includes(a);
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.25, y: ay, w: gw - 0.5, h: 0.5, rectRadius: 0.05, fill: { color: isHot ? C.teal : C.light }, line: { color: isHot ? C.teal : C.line, width: 1 } });
      s.addText([
        { text: isHot ? "★ " : "", options: { color: C.amber, bold: true } },
        { text: a, options: { color: isHot ? C.white : C.text, bold: isHot } },
      ], { x: x + 0.4, y: ay, w: gw - 0.7, h: 0.5, valign: "middle", fontFace: "Consolas", fontSize: 11.5, margin: 0 });
      ay += 0.58;
    });
    x += gw + ggap;
  });
  s.addText("★ = 与上海铁路通信场景最相关（SMT 换线 / 设备预测维护 / 质量追溯 / 经营驾驶舱 / IPC 合规 / 物料齐套 / 隐性知识）。", { x: 0.55, y: 6.7, w: 12.23, h: 0.4, fontFace: FB, fontSize: 11.5, italic: true, color: C.muted, margin: 0 });
  footer(s, 9);
})();

// ============ SLIDE 10 — 自我进化 ============
(function () {
  const s = pres.addSlide(); bg(s, C.light);
  header(s, "EVOLUTION · 自我进化", "自我进化：进化在资产层，越用越聪明");
  // loop
  const cyc = [["评估信号", 0.75], ["更新四类资产", 3.45], ["回灌认知", 6.15], ["下一轮更准", 8.85]];
  cyc.forEach(([t, cx3]) => {
    s.addShape(pres.shapes.OVAL, { x: cx3, y: 1.7, w: 2.0, h: 1.7, fill: { color: C.navy }, shadow: softShadow() });
    s.addText(t, { x: cx3, y: 1.7, w: 2.0, h: 1.7, align: "center", valign: "middle", fontFace: FH, fontSize: 14, bold: true, color: C.white, margin: 0 });
    if (cx3 < 8.85) s.addShape(pres.shapes.LINE, { x: cx3 + 2.0, y: 2.55, w: 1.45, h: 0, line: { color: C.teal, width: 2.5, endArrowType: "triangle" } });
  });
  // return arrow below: 下一轮更准 -> 评估信号
  s.addShape(pres.shapes.LINE, { x: 1.0, y: 3.7, w: 10.6, h: 0, line: { color: C.amber, width: 2.5, beginArrowType: "triangle" } });
  s.addText("自我进化回灌：执行结果驱动资产更新，下一轮判断更准", { x: 0.55, y: 3.85, w: 12.23, h: 0.35, align: "center", fontFace: FB, fontSize: 12, italic: true, color: C.tealD, margin: 0 });
  // asset step detail
  card(s, 0.55, 4.35, 12.23, 1.5, C.card);
  s.addText("四类资产被持续更新", { x: 0.8, y: 4.45, w: 5, h: 0.4, fontFace: FH, fontSize: 14, bold: true, color: C.navy, margin: 0 });
  const assets = [["记忆", "学到什么"], ["知识图谱", "知道什么关系"], ["技能", "能做什么"], ["策略阈值", "调优边界"]];
  let ax = 0.8;
  assets.forEach(([t, d]) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: ax, y: 4.95, w: 2.85, h: 0.75, rectRadius: 0.06, fill: { color: C.light }, line: { color: C.teal, width: 1 } });
    s.addText([{ text: t + "\n", options: { bold: true, color: C.tealD, fontSize: 13 } }, { text: d, options: { color: C.muted, fontSize: 10.5 } }], { x: ax, y: 4.95, w: 2.85, h: 0.75, align: "center", valign: "middle", fontFace: FH, margin: 0 });
    ax += 2.95;
  });
  // L0-L3 + north star
  card(s, 0.55, 6.0, 7.4, 0.85, C.navy);
  s.addText("进化阶梯：L0 静态种子 → L1 运行时事件 → L2 评估驱动 → L3 跨企业复利", { x: 0.8, y: 6.0, w: 7.0, h: 0.85, valign: "middle", fontFace: FB, fontSize: 12, color: C.ice, margin: 0 });
  card(s, 8.18, 6.0, 4.6, 0.85, C.teal);
  s.addText([{ text: "北极星 · 决策实时化率  ", options: { bold: true, color: C.white, fontSize: 12 } }, { text: "MVP≥40% → 稳态≥85%", options: { color: C.white, fontSize: 12 } }], { x: 8.4, y: 6.0, w: 4.2, h: 0.85, valign: "middle", fontFace: FH, margin: 0 });
  footer(s, 10);
})();

// ============ SLIDE 11 — 成熟度 L0-L3 ============
(function () {
  const s = pres.addSlide(); bg(s, C.light);
  header(s, "MATURITY · 成熟度模型", "智能分身成熟度：L0–L3，今天承诺到 L2");
  const lv = [
    ["L0", "观察", "采集与呈现，不给建议", C.navy],
    ["L1", "判断", "发生了什么 / 意味着什么", C.steel],
    ["L2", "预案", "可以怎么做（备选 + 权衡）", C.tealD],
    ["L3", "授权执行", "限定边界内自动回写", C.muted],
  ];
  let x = 0.55; const w = 2.95, gap = 0.13;
  lv.forEach(([l, nm, d, col], i) => {
    card(s, x, 1.8, w, 2.6, i === 3 ? C.light : C.card, { line: i === 3 ? C.muted : C.line });
    s.addShape(pres.shapes.RECTANGLE, { x: x, y: 1.8, w: w, h: 0.85, fill: { color: col } });
    s.addText([{ text: l + "  ", options: { fontSize: 22, bold: true } }, { text: nm, options: { fontSize: 15, bold: true } }], { x: x, y: 1.8, w: w, h: 0.85, align: "center", valign: "middle", fontFace: FH, color: C.white, margin: 0 });
    s.addText(d, { x: x + 0.2, y: 2.8, w: w - 0.4, h: 1.4, fontFace: FB, fontSize: 12.5, color: C.text, lineSpacingMultiple: 1.3, valign: "top", margin: 0 });
    if (i < 3) s.addShape(pres.shapes.LINE, { x: x + w + 0.01, y: 3.1, w: gap - 0.02, h: 0, line: { color: C.teal, width: 2, endArrowType: "triangle" } });
    x += w + gap;
  });
  // red line
  card(s, 0.55, 4.7, 12.23, 1.95, C.dark);
  s.addShape(pres.shapes.RECTANGLE, { x: 0.55, y: 4.7, w: 0.13, h: 1.95, fill: { color: C.amber } });
  s.addText("🔴 红线（对外不破）", { x: 0.85, y: 4.9, w: 11, h: 0.4, fontFace: FH, fontSize: 15, bold: true, color: C.amber, margin: 0 });
  s.addText([
    { text: "今日对外只承诺 L0–L2，绝不承诺 L3；", options: { bullet: { code: "2022" }, color: C.white, breakLine: true } },
    { text: "分身不得代签、不得代拍板——凡涉对外责任动作，人留终审；", options: { bullet: { code: "2022" }, color: C.white, breakLine: true } },
    { text: "任何「授权执行」都显式标注授权边界与人工复核点，不暗示全自动。", options: { bullet: { code: "2022" }, color: C.white } },
  ], { x: 0.9, y: 5.35, w: 11.6, h: 1.2, fontFace: FB, fontSize: 13, lineSpacingMultiple: 1.3, paraSpaceAfter: 5, margin: 0 });
  footer(s, 11);
})();

// ============ SLIDE 12 — 治理底座 ============
(function () {
  const s = pres.addSlide(); bg(s, C.light);
  header(s, "GOVERNANCE · 治理底座", "治理底座：可控 · 可审计 · 可平权");
  const g = [
    ["审批门（人在回路）", "高风险动作须人工确认，系统给预案、人拍板"],
    ["蓝弧闭环", "执行后果回流，每个决策可追踪、可验证"],
    ["权限三层", "角色—技能—授权等级绑定，授权 L0–L3 清晰"],
    ["匿名铁律", "对外案例一律匿名，真实锚定绝不外发"],
    ["凭证隔离", "密钥 vault 加密 + 租户隔离，不明文落库/外发"],
    ["回写审计", "ERP/MES 回写三合一审计，动作全程留痕"],
  ];
  let x = 0.55, y = 1.75; const w = 3.95, h = 1.5, gx = 0.19, gy = 0.2;
  g.forEach(([t, d], i) => {
    card(s, x, y, w, h);
    s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: y + 0.22, w: 0.5, h: 0.5, fill: { color: C.teal } });
    s.addText(String(i + 1), { x: x + 0.2, y: y + 0.22, w: 0.5, h: 0.5, align: "center", valign: "middle", fontFace: "Arial", fontSize: 15, bold: true, color: C.white, margin: 0 });
    s.addText(t, { x: x + 0.85, y: y + 0.2, w: w - 1.0, h: 0.5, fontFace: FH, fontSize: 14, bold: true, color: C.navy, margin: 0 });
    s.addText(d, { x: x + 0.85, y: y + 0.68, w: w - 1.0, h: 0.7, fontFace: FB, fontSize: 11.5, color: C.muted, lineSpacingMultiple: 1.2, margin: 0 });
    x += w + gx;
    if ((i + 1) % 3 === 0) { x = 0.55; y += h + gy; }
  });
  s.addText("对安全关键系统尤其关键：每个决策证据可追溯，重大动作必须审批——天然契合 SIL 认证的审计链要求。", { x: 0.55, y: 5.15, w: 12.23, h: 0.4, align: "center", fontFace: FB, fontSize: 12, italic: true, color: C.tealD, margin: 0 });
  footer(s, 12);
})();

// ============ SLIDE 13 — 开源开放 ============
(function () {
  const s = pres.addSlide(); bg(s, C.light);
  header(s, "OPEN SOURCE · 自主可控", "为什么全开源：不被锁定，信创可用");
  // left: Apache 2.0
  card(s, 0.55, 1.75, 6.0, 4.85, C.card);
  s.addShape(pres.shapes.RECTANGLE, { x: 0.55, y: 1.75, w: 6.0, h: 0.65, fill: { color: C.navy } });
  s.addText("Apache 2.0 意味着什么", { x: 0.55, y: 1.75, w: 6.0, h: 0.65, align: "center", valign: "middle", fontFace: FH, fontSize: 16, bold: true, color: C.white, margin: 0 });
  const ap = ["代码随便看、随便改、随便部署", "不被任何厂商锁定", "可做信创适配（自主可控硬约束）", "没有「授权费越用越贵」的陷阱", "智能体能力可审计、可验证"];
  s.addText(ap.map((t) => ({ text: t, options: { bullet: { code: "2022" }, breakLine: true, color: C.text } })), { x: 0.9, y: 2.6, w: 5.4, h: 3.8, fontFace: FB, fontSize: 14, lineSpacingMultiple: 1.5, paraSpaceAfter: 8, margin: 0 });
  // right: open system worldview
  card(s, 6.78, 1.75, 6.0, 4.85, C.navy);
  s.addShape(pres.shapes.RECTANGLE, { x: 6.78, y: 1.75, w: 0.13, h: 4.85, fill: { color: C.teal } });
  s.addText("开放系统世界观", { x: 7.1, y: 2.0, w: 5.4, h: 0.45, fontFace: FH, fontSize: 16, bold: true, color: C.teal, margin: 0 });
  s.addText("系统是开放的，不封闭。", { x: 7.1, y: 2.55, w: 5.4, h: 0.4, fontFace: FH, fontSize: 14, bold: true, color: C.white, margin: 0 });
  s.addText([
    { text: "宝库 / 预设库 = ", options: { color: C.ice } },
    { text: "开放获取加速层", options: { color: C.amber, bold: true } },
    { text: "——让你更快起步，不是封闭库存。", options: { color: C.ice, breakLine: true } },
    { text: "决策重心在内部：外部信息免费且清晰，内部数据稀缺且关键。", options: { color: C.ice, breakLine: true } },
    { text: "价值来自「外部清晰 + 内部贯通」的化合，而非囤数据。", options: { color: C.ice } },
  ], { x: 7.1, y: 3.1, w: 5.4, h: 3.2, fontFace: FB, fontSize: 13.5, lineSpacingMultiple: 1.4, margin: 0 });
  footer(s, 13);
})();

// ============ SLIDE 14 — 与铁路通信结合（核心） ============
(function () {
  const s = pres.addSlide(); bg(s, C.light);
  header(s, "COLLABORATION · 结合可能", "与上海铁路通信的结合可能：六个可落地场景");
  const rows = [
    ["SMT 换线优化", "smt_changeover", "多品种小批量换线时间缩短 30%+"],
    ["电子物料齐套预警", "supply_chain + wms_logistics", "缺料停产风险下降 50%+"],
    ["质量追溯 + IPC 合规", "quality_trace + ipc_standard", "通信板卡全流程追溯，满足 SIL 审计"],
    ["设备预测维护", "pm_maintenance + oee_optimizer", "非计划停机减少 40%"],
    ["隐性知识数字化", "tacit_capture", "技工经验自动沉淀，不随人走"],
    ["经营管控驾驶舱", "executive_cockpit", "跨域决策一屏掌握，实时化率提升"],
  ];
  const head = [
    { text: "场景", options: { fill: { color: C.navy }, color: "FFFFFF", bold: true, align: "center", fontSize: 13 } },
    { text: "涉及智能分身", options: { fill: { color: C.navy }, color: "FFFFFF", bold: true, align: "center", fontSize: 13 } },
    { text: "预期效果", options: { fill: { color: C.navy }, color: "FFFFFF", bold: true, align: "center", fontSize: 13 } },
  ];
  const body = rows.map((r, i) => {
    const fc = i % 2 === 0 ? "FFFFFF" : "EEF4F8";
    return [
      { text: r[0], options: { fill: { color: fc }, color: C.navy, bold: true, fontSize: 12.5, align: "left", valign: "middle" } },
      { text: r[1], options: { fill: { color: fc }, color: C.tealD, fontSize: 11, align: "left", valign: "middle", fontFace: "Consolas" } },
      { text: r[2], options: { fill: { color: fc }, color: C.text, fontSize: 12.5, align: "left", valign: "middle" } },
    ];
  });
  s.addTable([head, ...body], {
    x: 0.55, y: 1.8, w: 12.23, colW: [3.4, 4.0, 4.83],
    rowH: [0.5, 0.72, 0.72, 0.72, 0.72, 0.72, 0.72],
    border: { type: "solid", pt: 1, color: C.line }, valign: "middle", fontFace: FB,
  });
  footer(s, 14);
})();

// ============ SLIDE 15 — 安全关键 SIL 契合 ============
(function () {
  const s = pres.addSlide(); bg(s, C.light);
  header(s, "SAFETY · 安全关键系统", "铁路信号是安全关键系统：我们的设计天然契合");
  s.addText("铁路信号产品属 SIL（Safety Integrity Level）认证产品——任何 AI 决策不能黑箱。智衍的四项机制与之对齐：", { x: 0.55, y: 1.6, w: 12.23, h: 0.5, fontFace: FB, fontSize: 13.5, color: C.text, margin: 0 });
  const m = [
    ["AI 决策不可黑箱", "审批门机制", "系统给预案，人审批后才生效"],
    ["知识可审计", "每条 KG 事实有来源", "决策证据可追溯，满足审计链"],
    ["人在回路", "高风险动作人工审批", "凡涉责任，人留终审"],
    ["后果闭环", "每个决策可追踪效果", "执行结果回流，持续校准"],
  ];
  let x = 0.55, y = 2.3; const w = 6.0, h = 1.95, gx = 0.23, gy = 0.22;
  m.forEach(([a, b, c], i) => {
    card(s, x, y, w, h, C.card);
    s.addShape(pres.shapes.RECTANGLE, { x: x, y: y, w: 0.13, h: h, fill: { color: C.teal } });
    s.addText(a, { x: x + 0.3, y: y + 0.2, w: w - 0.5, h: 0.45, fontFace: FH, fontSize: 15, bold: true, color: C.navy, margin: 0 });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.3, y: y + 0.72, w: w - 0.6, h: 0.5, rectRadius: 0.06, fill: { color: C.light }, line: { color: C.teal, width: 1 } });
    s.addText(b, { x: x + 0.3, y: y + 0.72, w: w - 0.6, h: 0.5, align: "center", valign: "middle", fontFace: FH, fontSize: 13, bold: true, color: C.tealD, margin: 0 });
    s.addText(c, { x: x + 0.3, y: y + 1.3, w: w - 0.6, h: 0.55, fontFace: FB, fontSize: 12, color: C.muted, lineSpacingMultiple: 1.2, margin: 0 });
    x += w + gx;
    if ((i + 1) % 2 === 0) { x = 0.55; y += h + gy; }
  });
  footer(s, 15);
})();

// ============ SLIDE 16 — 合作路径 G 模式 ============
(function () {
  const s = pres.addSlide(); bg(s, C.light);
  header(s, "PATH · 合作路径", "合作路径：注册即入职，由浅入深（G 模式）");
  const ph = [
    ["外圈", "免费 · 零集成", "产业 / 行业级洞察，注册即有获得感（TTFV < 60s）", C.navy],
    ["中圈", "接入 1 源起", "企业级经营管控分身，接入贵司数据，跨域决策一屏掌握", C.steel],
    ["内圈", "私有化深度集成", "专业级岗位执行分身，深度集成产线 / 设备 / 工艺", C.teal],
  ];
  let x = 0.55; const w = 3.95, gap = 0.19;
  ph.forEach(([t, sub, d, col], i) => {
    card(s, x, 1.8, w, 3.2);
    s.addShape(pres.shapes.RECTANGLE, { x: x, y: 1.8, w: w, h: 0.9, fill: { color: col } });
    s.addText(t, { x: x, y: 1.8, w: w, h: 0.9, align: "center", valign: "middle", fontFace: FH, fontSize: 20, bold: true, color: C.white, margin: 0 });
    s.addText(sub, { x: x + 0.2, y: 2.85, w: w - 0.4, h: 0.45, align: "center", fontFace: FH, fontSize: 14, bold: true, color: C.tealD, margin: 0 });
    s.addText(d, { x: x + 0.25, y: 3.4, w: w - 0.5, h: 1.4, fontFace: FB, fontSize: 12.5, color: C.text, lineSpacingMultiple: 1.35, margin: 0 });
    if (i < 2) s.addShape(pres.shapes.LINE, { x: x + w - 0.05, y: 3.4, w: gap + 0.1, h: 0, line: { color: C.teal, width: 3.5, endArrowType: "triangle" } });
    x += w + gap;
  });
  card(s, 0.55, 5.25, 12.23, 1.4, C.navy);
  s.addShape(pres.shapes.RECTANGLE, { x: 0.55, y: 5.25, w: 0.13, h: 1.4, fill: { color: C.amber } });
  s.addText("建议起点", { x: 0.85, y: 5.4, w: 3, h: 0.4, fontFace: FH, fontSize: 14, bold: true, color: C.amber, margin: 0 });
  s.addText("先选 1–2 个岗位执行分身试点（如质量追溯 / 设备预测维护），注册即看到第一份经营判断；跑通后由中圈向内圈渐进深化。不用等招投标，今天就能开始。", { x: 0.85, y: 5.82, w: 11.6, h: 0.75, fontFace: FB, fontSize: 13, color: C.ice, lineSpacingMultiple: 1.3, margin: 0 });
  footer(s, 16);
})();

// ============ SLIDE 17 — Demo 指引 ============
(function () {
  const s = pres.addSlide(); bg(s, C.light);
  header(s, "TRY IT · 现场体验", "30 秒看到你的第一个决策孪生");
  const steps = [
    ["①", "打开体验环境", "http://43.153.172.52:3006"],
    ["②", "注册并选角色", "选一个经营 / 岗位分身，60 秒内看到首屏"],
    ["③", "看孪生大屏", "六路感知实时事件流一目了然"],
    ["④", "跑一条齐套检查", "自然语言提问，看分身如何分析并给预案"],
  ];
  let x = 0.55, y = 1.8; const w = 6.0, h = 1.55, gx = 0.23, gy = 0.22;
  steps.forEach(([n, t, d], i) => {
    card(s, x, y, w, h);
    s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: y + 0.45, w: 0.65, h: 0.65, fill: { color: C.teal } });
    s.addText(n, { x: x + 0.25, y: y + 0.45, w: 0.65, h: 0.65, align: "center", valign: "middle", fontFace: "Arial", fontSize: 20, bold: true, color: C.white, margin: 0 });
    s.addText(t, { x: x + 1.05, y: y + 0.25, w: w - 1.3, h: 0.5, fontFace: FH, fontSize: 15, bold: true, color: C.navy, margin: 0 });
    s.addText(d, { x: x + 1.05, y: y + 0.75, w: w - 1.3, h: 0.65, fontFace: FB, fontSize: 12, color: C.muted, lineSpacingMultiple: 1.2, margin: 0 });
    x += w + gx;
    if ((i + 1) % 2 === 0) { x = 0.55; y += h + gy; }
  });
  card(s, 0.55, 5.4, 12.23, 1.3, C.navy);
  s.addText([{ text: "开源仓库：", options: { color: C.teal, bold: true } }, { text: "github.com/iduyuhe/zhiyan-evolviq", options: { color: C.white, fontFace: "Consolas" } }, { text: "   （Apache 2.0，代码可看可改可部署）", options: { color: C.ice } }], { x: 0.85, y: 5.4, w: 11.6, h: 1.3, valign: "middle", fontFace: FH, fontSize: 14, margin: 0 });
  footer(s, 17);
})();

// ============ SLIDE 18 — 结语 ============
(function () {
  const s = pres.addSlide(); bg(s, C.dark);
  s.addShape(pres.shapes.OVAL, { x: 9.6, y: 4.6, w: 4.2, h: 4.2, fill: { color: C.dark }, line: { color: C.steel, width: 1.2 } });
  s.addShape(pres.shapes.OVAL, { x: 10.4, y: 5.4, w: 2.6, h: 2.6, fill: { color: C.dark }, line: { color: C.teal, width: 1.2 } });
  s.addText("结语", { x: 0.8, y: 1.2, w: 8, h: 0.5, fontFace: FB, fontSize: 14, color: C.teal, bold: true, charSpacing: 2, margin: 0 });
  s.addText([
    { text: "上 ERP 是让企业「知道自己有什么」；\n", options: { color: C.white, bold: true } },
    { text: "上智能体是让企业「自己就知道该怎么做」。", options: { color: C.white, bold: true } },
  ], { x: 0.8, y: 1.8, w: 9.5, h: 1.8, fontFace: FH, fontSize: 28, lineSpacingMultiple: 1.15, margin: 0 });
  s.addText("制造业的未来，不是更大更贵的软件，而是会自己长的智能体。", { x: 0.82, y: 3.8, w: 9.0, h: 0.6, fontFace: FB, fontSize: 15, color: C.ice, margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.82, y: 4.7, w: 2.2, h: 0.05, fill: { color: C.teal } });
  s.addText([
    { text: "现场体验：http://43.153.172.52:3006\n", options: { color: C.white, fontSize: 14, breakLine: true } },
    { text: "开源仓库：github.com/iduyuhe/zhiyan-evolviq\n", options: { color: C.ice, fontSize: 13, breakLine: true } },
    { text: "联系：杜玉河 · 工业5点0产业生态联盟", options: { color: C.ice, fontSize: 13 } },
  ], { x: 0.82, y: 4.95, w: 9.0, h: 1.5, fontFace: FB, lineSpacingMultiple: 1.4, margin: 0 });
})();

pres.writeFile({ fileName: "docs/智衍EvolvIQ_系统介绍_上海铁路通信有限公司.pptx" }).then((f) => {
  console.log("WROTE:", f);
}).catch((e) => { console.error("ERR", e); process.exit(1); });
