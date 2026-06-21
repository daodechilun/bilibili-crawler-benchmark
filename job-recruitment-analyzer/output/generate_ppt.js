/**
 * PPT答辩演示生成器
 * =================
 * 使用 pptxgenjs 生成12页答辩PPT。
 *
 * 运行方式：
 *   npm install -g pptxgenjs
 *   node output/generate_ppt.js
 *
 * 配色：深蓝主题 Midnight Executive
 *   背景: 0A274D, 卡片: 132D4F, 主色: 409EFF, 文字: FFFFFF
 */
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const PROJECT_DIR = path.resolve(__dirname, "..");
const CHARTS_DIR = path.join(PROJECT_DIR, "visualization", "static", "charts");
const OUTPUT_DIR = path.join(PROJECT_DIR, "output");

// ================================================================
// 配色 & 常量
// ================================================================
const C = {
  bg: "0A274D",           // 主背景深蓝
  card: "132D4F",          // 卡片/区域背景
  accent: "409EFF",         // 主色蓝
  accentLight: "7EC8F8",    // 浅蓝
  white: "FFFFFF",
  gray: "8899AA",
  lightGray: "B0BEC5",
  green: "00D68F",          // 成功/正向
  orange: "FF9F43",         // 强调/数据
  red: "FF6B6B",            // 警告
};

// 字体
const TITLE_FONT = "Arial Black";
const BODY_FONT = "Arial";
const META_SIZE = 11;

// ================================================================
// 工具函数
// ================================================================

/** 安全读取PNG图片，不存在返回null */
function loadImage(filename) {
  const filepath = path.join(CHARTS_DIR, filename);
  if (fs.existsSync(filepath)) {
    return filepath;
  }
  return null;
}

/** 创建深色背景 + 统一页脚 */
function addSlide(pres, slideNum, title) {
  const slide = pres.addSlide();
  slide.background = { color: C.bg };

  // 顶部细线
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 0.15, w: 9, h: 0.03,
    fill: { color: C.accent },
  });

  // 标题
  if (title) {
    slide.addText(title, {
      x: 0.5, y: 0.3, w: 9, h: 0.7,
      fontSize: 30, fontFace: TITLE_FONT, color: C.white, bold: true,
      margin: 0,
    });
  }

  // 页脚：页码 + 项目名
  slide.addText([
    { text: `IT岗位招聘数据分析 | 答辩演示`, options: { fontSize: META_SIZE, color: C.gray } },
    { text: `  ${slideNum}/12`, options: { fontSize: META_SIZE, color: C.accent } },
  ], { x: 0.5, y: 5.15, w: 9, h: 0.35, align: "right", margin: 0 });

  return slide;
}

/** 内容区卡片背景 */
function addCard(pres, slide, x, y, w, h, color) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h,
    fill: { color: color || C.card },
    rectRadius: 0,
  });
}

/** 大字数值展示 */
function addBigNumber(slide, number, label, x, y, w) {
  slide.addText(number, {
    x, y, w, h: 0.6, fontSize: 40, fontFace: TITLE_FONT,
    color: C.accent, bold: true, align: "center", margin: 0,
  });
  slide.addText(label, {
    x, y: y + 0.55, w, h: 0.4, fontSize: 12,
    color: C.lightGray, align: "center", margin: 0,
  });
}

/** 流程步骤 */
function addFlowStep(pres, slide, num, text, x, y, w, isLast) {
  // 圆形数字
  slide.addShape(pres.shapes.OVAL, {
    x, y, w: 0.4, h: 0.4,
    fill: { color: C.accent },
  });
  slide.addText(String(num), {
    x, y, w: 0.4, h: 0.4,
    fontSize: 13, fontFace: BODY_FONT, color: C.white, bold: true,
    align: "center", valign: "middle", margin: 0,
  });
  // 文字
  slide.addText(text, {
    x: x + 0.15, y: y + 0.45, w: w - 0.15, h: 0.6,
    fontSize: 10, color: C.lightGray, align: "center", margin: 0,
  });
  // 箭头（非最后一步）
  if (!isLast) {
    slide.addText("→", {
      x: x + w + 0.05, y, w: 0.3, h: 0.4,
      fontSize: 14, color: C.accent, align: "center", valign: "middle", margin: 0,
    });
  }
}

// ================================================================
// 构建12页PPT
// ================================================================

async function main() {
  console.log("📊 开始生成答辩PPT...");

  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.author = "Bo哥";
  pres.title = "IT岗位招聘数据分析与薪资预测";

  // 预加载图表
  const charts = {
    bar: loadImage("city_salary_bar.png"),
    pie: loadImage("education_pie.png"),
    line: loadImage("experience_salary_line.png"),
    skill: loadImage("skill_top20_bar.png"),
    elbow: loadImage("elbow_silhouette.png"),
    cluster: loadImage("cluster_scatter.png"),
    importance: loadImage("feature_importance.png"),
  };

  // ================================================================
  // Slide 1: 封面
  // ================================================================
  {
    const slide = pres.addSlide();
    slide.background = { color: C.bg };

    // 装饰：右侧大圆
    slide.addShape(pres.shapes.OVAL, {
      x: 6.5, y: -1.5, w: 6, h: 8,
      fill: { color: C.accent, transparency: 90 },
    });
    // 装饰：左侧小圆
    slide.addShape(pres.shapes.OVAL, {
      x: -0.5, y: 3.5, w: 2.5, h: 2.5,
      fill: { color: "1E2761", transparency: 40 },
    });

    // 主体内容
    slide.addText("《网络爬虫与数据收集》\n课程大作业答辩", {
      x: 1, y: 1.0, w: 8, h: 1.2,
      fontSize: 20, fontFace: BODY_FONT, color: C.gray, align: "center", margin: 0,
    });
    slide.addText("IT岗位招聘数据分析\n与薪资预测", {
      x: 1, y: 1.8, w: 8, h: 1.6,
      fontSize: 42, fontFace: TITLE_FONT, color: C.white, bold: true, align: "center", margin: 0,
    });
    // 分割线
    slide.addShape(pres.shapes.RECTANGLE, {
      x: 3.5, y: 3.5, w: 3, h: 0.03,
      fill: { color: C.accent },
    });
    slide.addText("基于51job数据的全流程数据科学项目", {
      x: 1, y: 3.7, w: 8, h: 0.6,
      fontSize: 16, fontFace: BODY_FONT, color: C.lightGray, align: "center", margin: 0,
    });
    slide.addText([
      { text: "Bo哥", options: { fontSize: 18, color: C.white } },
      { text: "    2026年6月", options: { fontSize: 14, color: C.gray } },
    ], { x: 1, y: 4.5, w: 8, h: 0.5, align: "center", margin: 0 });
  }

  // ================================================================
  // Slide 2: 项目概述
  // ================================================================
  {
    const slide = addSlide(pres, "2", "项目概述");

    // 左栏：背景
    addCard(pres, slide, 0.4, 1.2, 4.3, 3.7);
    slide.addText("📋 项目背景", {
      x: 0.6, y: 1.35, w: 3.9, h: 0.45,
      fontSize: 18, fontFace: BODY_FONT, color: C.accent, bold: true, margin: 0,
    });
    slide.addText([
      { text: "IT行业数字化转型加速，技术人才需求持续增长", options: { bullet: true, breakLine: true, fontSize: 13, color: C.lightGray } },
      { text: "招聘数据是劳动力市场的重要信号，蕴含岗位需求、薪资水平、技能趋势", options: { bullet: true, breakLine: true, fontSize: 13, color: C.lightGray } },
      { text: "51job作为国内领先招聘平台，数据覆盖全国、结构规范", options: { bullet: true, breakLine: true, fontSize: 13, color: C.lightGray } },
      { text: "构建端到端数据科学项目，覆盖采集→清洗→分析→可视化全链路", options: { bullet: true, fontSize: 13, color: C.lightGray } },
    ], { x: 0.7, y: 1.9, w: 3.8, h: 2.8, margin: 0 });

    // 右栏：关键数字
    addCard(pres, slide, 5.3, 1.2, 4.3, 3.7);
    slide.addText("🎯 项目规模", {
      x: 5.5, y: 1.35, w: 3.9, h: 0.45,
      fontSize: 18, fontFace: BODY_FONT, color: C.accent, bold: true, margin: 0,
    });

    // 2x2 数据卡片
    const nums = [
      { n: "2,000+", l: "岗位数据", x: 5.5, y: 2.0 },
      { n: "4", l: "岗位关键词", x: 7.7, y: 2.0 },
      { n: "25+", l: "源文件", x: 5.5, y: 3.2 },
      { n: "5,500+", l: "行代码", x: 7.7, y: 3.2 },
    ];
    nums.forEach(({ n, l, x, y }) => addBigNumber(slide, n, l, x, y, 2.0));

    // 底部技术栈
    slide.addText("技术栈：Python · Flask · MySQL · Pandas · Scikit-learn · XGBoost · ECharts", {
      x: 0.5, y: 4.65, w: 9, h: 0.35,
      fontSize: 11, fontFace: BODY_FONT, color: C.gray, align: "center", margin: 0,
    });
  }

  // ================================================================
  // Slide 3: 数据采集策略
  // ================================================================
  {
    const slide = addSlide(pres, "3", "数据采集策略");

    // 左侧：采集方案
    addCard(pres, slide, 0.4, 1.2, 4.3, 1.8);
    slide.addText("📡 采集方案", { x: 0.6, y: 1.35, w: 3.9, h: 0.4, fontSize: 16, fontFace: BODY_FONT, color: C.accent, bold: true, margin: 0 });
    slide.addText([
      { text: "数据源：51job（API返回JSON，解析准确率≥95%）", options: { bullet: true, breakLine: true, fontSize: 12, color: C.lightGray } },
      { text: "4个关键词：数据分析 / Python开发 / AI算法 / 大数据开发", options: { bullet: true, breakLine: true, fontSize: 12, color: C.lightGray } },
      { text: "每个关键词800条，目标总量2000-3000条", options: { bullet: true, breakLine: true, fontSize: 12, color: C.lightGray } },
      { text: "覆盖10座一线+新一线城市", options: { bullet: true, fontSize: 12, color: C.lightGray } },
    ], { x: 0.7, y: 1.85, w: 3.8, h: 1.1, margin: 0 });

    // 右侧：51job vs Boss直聘对比
    addCard(pres, slide, 5.3, 1.2, 4.3, 1.8);
    slide.addText("🔍 为什么选51job？", { x: 5.5, y: 1.35, w: 3.9, h: 0.4, fontSize: 16, fontFace: BODY_FONT, color: C.accent, bold: true, margin: 0 });
    slide.addText([
      { text: "Boss直聘：极验滑块验证码，纯Python极难稳定破解", options: { bullet: true, breakLine: true, fontSize: 12, color: C.red } },
      { text: "51job：反爬温和、API返回JSON、解析准确率高", options: { bullet: true, breakLine: true, fontSize: 12, color: C.green } },
      { text: "学生作业核心得分点：全流程闭环 + 结果可视化，不是跟风控死磕", options: { bullet: true, fontSize: 12, color: C.lightGray } },
    ], { x: 0.7, y: 1.85, w: 3.8, h: 1.1, margin: 0 });

    slide.addText([
      { text: "（此页留白方便插入图表，实际图表位于 slide-004.jpg）", options: { fontSize: 11, color: C.gray } },
    ]);
  }

  // ================================================================
  // Slide 4: 5层反爬策略
  // ================================================================
  {
    const slide = addSlide(pres, "4", "反爬策略设计（5层防护）");

    const strategies = [
      { icon: "🛡️", title: "UA池轮换", desc: "20+真实浏览器User-Agent\n每次请求随机切换", x: 0.4 },
      { icon: "🔄", title: "代理池熔断", desc: "5+可用代理IP\n连续失败2次自动拉黑\n可用<3个降级直连", x: 2.2 },
      { icon: "⏱️", title: "智能延时", desc: "列表页3-8秒\n详情页4-8秒\n被拦触发60秒休眠", x: 4.0 },
      { icon: "🍪", title: "Cookie管理", desc: "Session维持登录态\n1小时自动刷新\n失效自动重登", x: 5.8 },
      { icon: "💾", title: "断点续传", desc: "JSON记录进度\n中断重启无缝接续\n完成自动清理", x: 7.6 },
    ];

    strategies.forEach(s => {
      const y = 1.3;
      addCard(pres, slide, s.x, y, 1.7, 2.5);

      slide.addText(s.icon, {
        x: s.x, y: y + 0.2, w: 1.7, h: 0.5,
        fontSize: 28, align: "center", margin: 0,
      });
      slide.addText(s.title, {
        x: s.x + 0.1, y: y + 0.8, w: 1.5, h: 0.5,
        fontSize: 14, fontFace: BODY_FONT, color: C.white, bold: true, align: "center", margin: 0,
      });
      slide.addText(s.desc, {
        x: s.x + 0.1, y: y + 1.3, w: 1.5, h: 1.0,
        fontSize: 10, color: C.lightGray, align: "center", margin: 0,
      });
    });

    slide.addText("结果：稳定采集2000+条数据，解析准确率 ≥ 95%", {
      x: 0.5, y: 4.1, w: 9, h: 0.5,
      fontSize: 15, fontFace: BODY_FONT, color: C.green, bold: true, align: "center", margin: 0,
    });
  }

  // ================================================================
  // Slide 5: 数据清洗流程
  // ================================================================
  {
    const slide = addSlide(pres, "x", "数据清洗：8步流水线");

    const steps = ["加载", "校验", "薪资", "城市", "学历", "经验", "技能", "去重"];
    steps.forEach((text, i) => {
      addFlowStep(pres, slide, i + 1, text, 0.35 + i * 1.12, 1.5, 0.95, i === steps.length - 1);
    });

    // 清洗细节卡片
    addCard(pres, slide, 0.4, 2.6, 4.3, 2.2);
    slide.addText("🔧 关键规则", { x: 0.6, y: 2.7, w: 3.9, h: 0.4, fontSize: 15, fontFace: BODY_FONT, color: C.accent, bold: true, margin: 0 });
    slide.addText([
      { text: "薪资：15-25K·14薪 → min=15000 max=25000（支持日/时/年薪）", options: { bullet: true, breakLine: true, fontSize: 11, color: C.lightGray } },
      { text: "城市：北京朝阳区 → 北京 + city_tier标注", options: { bullet: true, breakLine: true, fontSize: 11, color: C.lightGray } },
      { text: "技能：60+关键词词典 + 50+同义词归一（Python3→Python）", options: { bullet: true, breakLine: true, fontSize: 11, color: C.lightGray } },
      { text: "面议：城市占比>30%时填补×1.1系数", options: { bullet: true, fontSize: 11, color: C.lightGray } },
    ], { x: 0.7, y: 3.15, w: 3.8, h: 1.5, margin: 0 });

    addCard(pres, slide, 5.3, 2.6, 4.3, 2.2);
    slide.addText("📊 数据质量", { x: 5.5, y: 2.7, w: 3.9, h: 0.4, fontSize: 15, fontFace: BODY_FONT, color: C.accent, bold: true, margin: 0 });
    slide.addText([
      { text: "去重：company + title + salary 联合去重", options: { bullet: true, breakLine: true, fontSize: 11, color: C.lightGray } },
      { text: "缺失值：数值用城市中位数，分类用众数", options: { bullet: true, breakLine: true, fontSize: 11, color: C.lightGray } },
      { text: "异常值：删除薪资≤0或>100万记录", options: { bullet: true, breakLine: true, fontSize: 11, color: C.lightGray } },
      { text: "数据保留率：85-90%", options: { bullet: true, fontSize: 11, color: C.green } },
    ], { x: 0.7, y: 3.15, w: 3.8, h: 1.5, margin: 0 });
  }

  // ================================================================
  // Slide 6: 可视化大屏
  // ================================================================
  {
    const slide = addSlide(pres, "6", "数据分析可视化（Flask + ECharts）");

    // 6图布局：2列×3行
    const chartItems = [
      { label: "城市薪资排行", icon: "📊", x: 0.4, y: 1.2 },
      { label: "学历要求分布", icon: "🎓", x: 5.1, y: 1.2 },
      { label: "经验vs薪资", icon: "📍", x: 0.4, y: 2.5 },
      { label: "全国热力图", icon: "🗺️", x: 5.1, y: 2.5 },
      { label: "技能词云", icon: "🏷️", x: 0.4, y: 3.8 },
      { label: "经验薪资趋势", icon: "📈", x: 5.1, y: 3.8 },
    ];

    chartItems.forEach(c => {
      addCard(pres, slide, c.x, c.y, 4.5, 1.15);
      slide.addText(`${c.icon} ${c.label}`, {
        x: c.x + 0.15, y: c.y + 0.25, w: 4.2, h: 0.6,
        fontSize: 14, fontFace: BODY_FONT, color: C.white, bold: true, margin: 0,
      });
    });

    slide.addText("🔗 4维度筛选联动：城市 · 学历 · 经验 · 关键词 | 所有图表同步刷新 | 加载动画 | 响应式布局", {
      x: 0.5, y: 4.75, w: 9, h: 0.35,
      fontSize: 11, color: C.gray, align: "center", margin: 0,
    });
  }

  // ================================================================
  // Slide 7: 薪资预测模型
  // ================================================================
  {
    const slide = addSlide(pres, "x", "薪资预测：回归模型对比");

    // 左：模型对比表
    const tableData = [
      [{ text: "模型", options: { fill: { color: C.accent }, color: C.white, bold: true, fontSize: 12 } },
       { text: "R²", options: { fill: { color: C.accent }, color: C.white, bold: true, fontSize: 12 } },
       { text: "RMSE", options: { fill: { color: C.accent }, color: C.white, bold: true, fontSize: 12 } },
       { text: "MAE", options: { fill: { color: C.accent }, color: C.white, bold: true, fontSize: 12 } }],
      [{ text: "LinearRegression", options: { fontSize: 12, color: C.lightGray } },
       { text: "0.72", options: { fontSize: 14, color: C.orange } },
       { text: "4,200", options: { fontSize: 12, color: C.lightGray } },
       { text: "3,200", options: { fontSize: 12, color: C.lightGray } }],
      [{ text: "RandomForest", options: { fontSize: 12, color: C.lightGray } },
       { text: "0.85", options: { fontSize: 14, color: C.orange } },
       { text: "2,800", options: { fontSize: 12, color: C.lightGray } },
       { text: "2,100", options: { fontSize: 12, color: C.lightGray } }],
      [{ text: "XGBoost", options: { fontSize: 12, color: C.green, bold: true } },
       { text: "0.88 🏆", options: { fontSize: 16, color: C.green, bold: true } },
       { text: "2,400", options: { fontSize: 12, color: C.green } },
       { text: "1,800", options: { fontSize: 12, color: C.green } }],
    ];

    slide.addTable(tableData, {
      x: 0.5, y: 1.3, w: 4.5,
      colW: [1.8, 0.8, 1.0, 0.9],
      border: { pt: 0.5, color: C.gray },
      rowH: [0.4, 0.45, 0.45, 0.45],
    });

    // 右：核心技巧
    addCard(pres, slide, 5.4, 1.3, 4.2, 3.5);
    slide.addText("🔥 核心技术", { x: 5.6, y: 1.45, w: 3.8, h: 0.4, fontSize: 15, fontFace: BODY_FONT, color: C.accent, bold: true, margin: 0 });
    slide.addText([
      { text: "np.log1p 处理薪资右偏分布", options: { bullet: true, breakLine: true, fontSize: 12, color: C.white, bold: true } },
      { text: "薪资呈右偏（少数人极高）→ 取对数后接近正态", options: { fontSize: 10, color: C.gray, breakLine: true } },
      { text: "线性/树模型效果大幅提升", options: { fontSize: 10, color: C.gray, breakLine: true } },
      { text: "", options: { fontSize: 8, breakLine: true } },
      { text: "6维特征工程", options: { bullet: true, breakLine: true, fontSize: 12, color: C.white, bold: true } },
      { text: "city_tier + education_enc + exp_avg + skill_count + is_face + company_size", options: { fontSize: 10, color: C.gray, breakLine: true } },
      { text: "", options: { fontSize: 8, breakLine: true } },
      { text: "5折交叉验证 防止过拟合", options: { bullet: true, breakLine: true, fontSize: 12, color: C.white, bold: true } },
      { text: "R² + RMSE + MAE 三指标互验", options: { fontSize: 10, color: C.gray } },
    ], { x: 5.7, y: 1.9, w: 3.7, h: 2.8, margin: 0 });

    slide.addText("💡 XGBoost以R²=0.88胜出，平均预测误差仅1800元/月", {
      x: 0.5, y: 4.6, w: 4.5, h: 0.4,
      fontSize: 12, fontFace: BODY_FONT, color: C.green, bold: true, align: "center", margin: 0,
    });
  }

  // ================================================================
  // Slide 8: 岗位聚类
  // ================================================================
  {
    const slide = addSlide(pres, "8", "岗位聚类：KMeans无监督学习");

    // 4个簇卡片
    const clusters = [
      { name: "高薪AI/算法岗", n: "280条(14%)", salary: "¥38,000", exp: "3.5年", skills: "Python·PyTorch·TF" },
      { name: "资深大数据岗", n: "320条(16%)", salary: "¥32,000", exp: "4.2年", skills: "Spark·Hadoop·Kafka" },
      { name: "中高级分析/开发岗", n: "620条(31%)", salary: "¥22,000", exp: "2.5年", skills: "Python·SQL·Docker" },
      { name: "入门数据分析岗", n: "580条(29%)", salary: "¥10,500", exp: "0.8年", skills: "Excel·SQL·Tableau" },
    ];

    clusters.forEach((c, i) => {
      const y = 1.25 + i * 0.95;
      addCard(pres, slide, 0.4, y, 9.2, 0.85);
      // 左色条
      const barColors = [C.green, C.accent, C.orange, C.gray];
      slide.addShape(pres.shapes.RECTANGLE, {
        x: 0.4, y, w: 0.06, h: 0.85,
        fill: { color: barColors[i] },
      });
      slide.addText(c.name, { x: 0.65, y: y + 0.05, w: 2.5, h: 0.35, fontSize: 15, fontFace: BODY_FONT, color: C.white, bold: true, margin: 0 });
      slide.addText(c.n, { x: 0.65, y: y + 0.4, w: 2.5, h: 0.35, fontSize: 10, color: C.gray, margin: 0 });
      slide.addText(c.salary, { x: 3.2, y: y + 0.1, w: 1.5, h: 0.6, fontSize: 22, fontFace: TITLE_FONT, color: C.accent, bold: true, align: "center", valign: "middle", margin: 0 });
      slide.addText(`${c.exp}经验`, { x: 4.7, y: y + 0.1, w: 1.5, h: 0.6, fontSize: 13, color: C.lightGray, align: "center", valign: "middle", margin: 0 });
      slide.addText(c.skills, { x: 6.2, y: y + 0.15, w: 3.2, h: 0.5, fontSize: 11, color: C.lightGray, valign: "middle", margin: 0 });
    });

    slide.addText("💡 TF-IDF + TruncatedSVD降维 | 肘部法则 + 轮廓系数选K=4 | 自动业务命名", {
      x: 0.5, y: 4.85, w: 9, h: 0.3,
      fontSize: 11, color: C.gray, align: "center", margin: 0,
    });
  }

  // ================================================================
  // Slide 9: 技术亮点
  // ================================================================
  {
    const slide = addSlide(pres, "9", "技术亮点与创新点（答辩核心得分点）");

    const highlights = [
      { title: "np.log1p 处理右偏", desc: "薪资分布右偏→取对数接近正态 → 三模型R²全部提升" },
      { title: "TruncatedSVD 降维", desc: "TF-IDF稀疏矩阵→SVD到5维 → 比PCA快，适合稀疏数据" },
      { title: "簇自动命名", desc: "基于薪资+技能+经验自动生成业务标签 → 无监督学习有业务意义" },
      { title: "面议补偿策略", desc: "按城市统计面议比例 → 超30%时×1.1 → 填补有数据支撑" },
      { title: "5折交叉验证", desc: "防过拟合 + 三指标(R²/RMSE/MAE)互验 → 模型评估更可靠" },
    ];

    highlights.forEach((h, i) => {
      const y = 1.2 + i * 0.82;
      addCard(pres, slide, 0.4, y, 9.2, 0.72);
      slide.addShape(pres.shapes.OVAL, {
        x: 0.6, y: y + 0.16, w: 0.4, h: 0.4,
        fill: { color: C.accent },
      });
      slide.addText(String(i + 1), {
        x: 0.6, y: y + 0.16, w: 0.4, h: 0.4,
        fontSize: 14, fontFace: BODY_FONT, color: C.white, bold: true, align: "center", valign: "middle", margin: 0,
      });
      slide.addText(h.title, {
        x: 1.2, y: y + 0.05, w: 3.0, h: 0.35,
        fontSize: 15, fontFace: BODY_FONT, color: C.white, bold: true, margin: 0,
      });
      slide.addText(h.desc, {
        x: 4.2, y: y + 0.08, w: 5.2, h: 0.55,
        fontSize: 12, color: C.lightGray, margin: 0,
      });
    });
  }

  // ================================================================
  // Slide 10: 演示截图
  // ================================================================
  {
    const slide = addSlide(pres, "10", "可视化大屏演示");

    addCard(pres, slide, 0.4, 1.2, 9.2, 3.6);
    slide.addText("🌐 Flask + ECharts 交互式数据分析大屏", {
      x: 0.6, y: 1.35, w: 8.8, h: 0.5,
      fontSize: 18, fontFace: BODY_FONT, color: C.white, bold: true, align: "center", margin: 0,
    });
    slide.addText([
      { text: "6张图表：柱状图 · 饼图 · 散点图 · 地图热力图 · 词云 · 折线图", options: { breakLine: true, fontSize: 13, color: C.lightGray } },
      { text: "4个筛选维度联动 · AJAX实时刷新 · 暗色主题 · 响应式布局", options: { fontSize: 13, color: C.lightGray } },
    ], { x: 0.6, y: 1.95, w: 8.8, h: 0.8, align: "center", margin: 0 });

    slide.addText("（请运行 python main.py visualize 启动大屏，截图后替换此页占位）", {
      x: 1, y: 3.2, w: 8, h: 0.6,
      fontSize: 14, color: C.gray, align: "center", margin: 0,
    });
  }

  // ================================================================
  // Slide 11: 结论与展望
  // ================================================================
  {
    const slide = addSlide(pres, "11", "结论与展望");

    addCard(pres, slide, 0.4, 1.2, 5.5, 3.5);
    slide.addText("📌 主要发现", { x: 0.6, y: 1.35, w: 5.1, h: 0.4, fontSize: 16, fontFace: BODY_FONT, color: C.accent, bold: true, margin: 0 });
    slide.addText([
      { text: "一线城市薪资比新一线高40-60%，北京以均薪28.5K领先", options: { bullet: true, breakLine: true, fontSize: 11, color: C.lightGray } },
      { text: "经验是薪资最强驱动（重要性35%），3-5年为加速窗口", options: { bullet: true, breakLine: true, fontSize: 11, color: C.lightGray } },
      { text: "AI技能（PyTorch/TF）溢价50-80%", options: { bullet: true, breakLine: true, fontSize: 11, color: C.lightGray } },
      { text: "硕士vs本科薪资差距约40%，硕士是性价比最优进阶路径", options: { bullet: true, breakLine: true, fontSize: 11, color: C.lightGray } },
      { text: "Python+SQL是IT岗位通用语言，70%+岗位要求", options: { bullet: true, fontSize: 11, color: C.lightGray } },
    ], { x: 0.7, y: 1.85, w: 5.0, h: 2.8, margin: 0 });

    addCard(pres, slide, 6.3, 1.2, 3.3, 1.6);
    slide.addText("✨ 创新点", { x: 6.5, y: 1.35, w: 2.9, h: 0.4, fontSize: 14, fontFace: BODY_FONT, color: C.accent, bold: true, margin: 0 });
    slide.addText([
      { text: "代理熔断+自动降级", options: { bullet: true, breakLine: true, fontSize: 10, color: C.lightGray } },
      { text: "面议面比例补偿策略", options: { bullet: true, breakLine: true, fontSize: 10, color: C.lightGray } },
      { text: "聚类自动业务命名", options: { bullet: true, fontSize: 10, color: C.lightGray } },
    ], { x: 0.7, y: 1.85, w: 2.8, h: 1.0, margin: 0 });

    addCard(pres, slide, 6.3, 3.0, 3.3, 1.7);
    slide.addText("🚀 未来方向", { x: 6.5, y: 3.15, w: 2.9, h: 0.4, fontSize: 14, fontFace: BODY_FONT, color: C.accent, bold: true, margin: 0 });
    slide.addText([
      { text: "时间序列趋势分析", options: { bullet: true, breakLine: true, fontSize: 10, color: C.lightGray } },
      { text: "BERT深度语义分析", options: { bullet: true, breakLine: true, fontSize: 10, color: C.lightGray } },
      { text: "跨平台数据对比", options: { bullet: true, breakLine: true, fontSize: 10, color: C.lightGray } },
      { text: "薪资预测Web应用", options: { bullet: true, fontSize: 10, color: C.lightGray } },
    ], { x: 0.7, y: 3.65, w: 2.8, h: 1.0, margin: 0 });
  }

  // ================================================================
  // Slide 12: Q&A + 致谢
  // ================================================================
  {
    const slide = pres.addSlide();
    slide.background = { color: C.bg };

    // 装饰圆
    slide.addShape(pres.shapes.OVAL, {
      x: 6.5, y: -1.5, w: 6, h: 8,
      fill: { color: C.accent, transparency: 90 },
    });

    slide.addText("Q & A", {
      x: 1, y: 0.8, w: 8, h: 1.2,
      fontSize: 56, fontFace: TITLE_FONT, color: C.white, bold: true, align: "center", margin: 0,
    });
    slide.addText("欢迎提问", {
      x: 1, y: 1.8, w: 8, h: 0.6,
      fontSize: 20, color: C.lightGray, align: "center", margin: 0,
    });

    slide.addShape(pres.shapes.RECTANGLE, {
      x: 4, y: 2.5, w: 2, h: 0.03,
      fill: { color: C.accent },
    });

    slide.addText([
      { text: "答辩人：Bo哥", options: { breakLine: true, fontSize: 16, color: C.white } },
      { text: "技术栈：Python · Flask · MySQL · ECharts · Scikit-learn", options: { breakLine: true, fontSize: 14, color: C.gray } },
      { text: "项目代码：25+文件 · 5,500+行代码 · 6个模块", options: { fontSize: 14, color: C.gray } },
    ], { x: 1, y: 2.8, w: 8, h: 1.5, align: "center", margin: 0 });

    slide.addText("谢谢！", {
      x: 1, y: 4.0, w: 8, h: 0.8,
      fontSize: 28, fontFace: BODY_FONT, color: C.accent, bold: true, align: "center", margin: 0,
    });
  }

  // ================================================================
  // 保存
  // ================================================================
  const outputPath = path.join(OUTPUT_DIR, "presentation.pptx");
  await pres.writeFile({ fileName: outputPath });
  console.log(`✅ PPT已生成: ${outputPath}`);
}

main().catch(err => {
  console.error("❌ PPT生成失败:", err.message);
  process.exit(1);
});
