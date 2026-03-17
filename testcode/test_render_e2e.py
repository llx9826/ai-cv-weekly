"""End-to-end Rendering Test

Generates HTML files from mock Markdown to verify the Tailwind + DaisyUI
template rendering works correctly for all report types.

Usage:
    python -m testcode.test_render_e2e
"""

from pathlib import Path
from datetime import datetime

from brief.presets import get_preset
from brief.models import ReportDraft
from brief.renderer.jinja2 import Jinja2Renderer


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output" / "render_test"

MOCK_AI_WEEKLY = """\
## 📌 核心判断

> 本周 AI 领域最大看点：多模态 Agent 框架井喷式涌现，OpenAI、Google、Anthropic 三大厂同时发力；OCR/文档理解赛道出现两个重要开源项目。

## 一、本周核心结论

### 1. 多模态 Agent 框架成为新战场

**结论**：OpenAI 发布 Operator SDK，Google 开源 Gemini Agent Toolkit，Agent 框架从概念验证进入工程化阶段。
**依据**：三大厂均在本周发布了 Agent 相关框架，GitHub star 增速远超传统 LLM 项目。
**约束**：目前框架间互操作性差，生态碎片化风险不容忽视。

**🦞 Claw 锐评**：Agent 框架的竞争本质是 API 生态之争。谁能先建立开发者习惯，谁就掌握下一代 AI 应用的入口。

### 2. OCR/文档 AI 开源生态加速

**结论**：GOT-OCR2.0 和 DocLayout-YOLO 两个项目同周开源，分别在端到端文档理解和版面分析方向取得突破。
**依据**：GOT-OCR2.0 在多个基准测试上超越商用方案，DocLayout-YOLO 推理速度提升 3 倍。
**约束**：模型精度在复杂排版场景（如财务报表）仍有 10-15% 差距。

**🦞 Claw 锐评**：OCR 赛道的开源追赶速度超出预期。商业 OCR 服务如果不能在垂直场景建立壁垒，两年内可能被蚕食大半市场。

### 3. Vision-Language Model 进入「实用化」拐点

**结论**：本周多个 VLM 在实际业务场景中展示了可用的精度和速度指标。
**依据**：InternVL2-26B 在多语言文档理解任务上达到 GPT-4V 的 95% 水平，推理成本仅为十分之一。
**约束**：长文档（>20页）处理仍然是瓶颈，context window 限制明显。

## 二、重点事件

### 1. OpenAI 发布 Operator SDK

**事件**：OpenAI 正式开源 Operator SDK，支持构建可执行多步骤任务的 AI Agent。
**影响**：降低 Agent 开发门槛，预计催生大量 AI 工作流自动化应用。
**数据**：发布 48 小时内 GitHub star 突破 15,000。

**🦞 Claw 锐评**：SDK 质量高但锁定 OpenAI 生态。建议技术团队同时评估 LangChain 和 CrewAI 作为多云方案。

### 2. Google DeepMind 发布 Gemini 2.5 Pro

**事件**：Gemini 2.5 Pro 在多模态推理基准测试中全面超越 GPT-4o。
**影响**：多模态大模型竞争进入白热化阶段。
**数据**：MMMU benchmark 得分 74.2%，超过 GPT-4o 的 69.1%。

### 3. Meta 开源 LLaMA 4

**事件**：Meta 开源 LLaMA 4 系列，包含 Scout (109B) 和 Maverick (400B) 两个版本。
**影响**：开源阵营首次在推理能力上接近闭源前沿水平。
**数据**：Maverick 在 GPQA 得分 69.8%，接近 Claude 3.5 Sonnet。

## 三、开源项目推荐

### 1. GOT-OCR2.0

**类型**：端到端 OCR 模型
**亮点**：支持场景文字、文档、数学公式一体化识别
**GitHub**：github.com/Ucas-HaoranWei/GOT-OCR2.0
**Star 增速**：+2,400/周

**🦞 Claw 锐评**：终于有一个开源方案能和 Azure Document Intelligence 正面对决了。

### 2. DocLayout-YOLO

**类型**：文档版面分析
**亮点**：基于 YOLO 架构，推理速度达到 200fps
**GitHub**：github.com/opendatalab/DocLayout-YOLO
**Star 增速**：+1,800/周

## 四、论文推荐

### 1. Florence-2: Advancing a Unified Representation for Vision Tasks

**来源**：CVPR 2024 Best Paper
**核心贡献**：统一视觉表示框架，单模型处理检测/分割/OCR/描述等多任务
**意义**：为 Foundation Model 在 CV 领域的统一提供了新范式

### 2. Qwen2-VL: Enhancing Vision-Language Model's Perception

**来源**：arXiv 2024
**核心贡献**：动态分辨率处理 + 视频理解能力
**意义**：VLM 开源社区的新标杆，中文场景表现尤为突出

## 五、趋势分析

- **Agent 框架生态加速整合**：预计 6 个月内出现 2-3 个头部标准化框架
- **OCR 开源追赶商用**：开源 OCR 方案正在缩小与商用服务的差距，预计年底基本持平
- **VLM 从实验到生产**：视觉语言模型开始被嵌入实际产品管线
- **多模态训练数据成为瓶颈**：高质量对齐数据的稀缺性将成为模型能力的真正分水岭

## 六、技术趋势策略

- **当前阶段**：技术扩散期，适合布局 Agent + 多模态方向
- **避免**：过早押注单一 Agent 框架，生态尚未收敛
- **避免**：忽视开源 OCR 的追赶速度
- **关注**：VLM 在垂直行业（医疗、金融、法律）的落地案例
- **关注**：多模态数据标注/合成赛道的创业机会
"""

MOCK_FINANCE_DAILY = """\
## 📌 核心判断

> 美联储暂停加息信号明确，科技股领涨大盘；关注本周五 PCE 数据发布对市场节奏的影响。

## 一、市场要闻

### 1. 美联储 3 月会议纪要释放鸽派信号

**事件**：FOMC 会议纪要显示多数委员支持年内至少降息一次。
**影响**：美股三大指数齐涨，纳斯达克涨幅 +1.8%。
**数据**：10 年期美债收益率回落至 4.15%。

**🦞 Claw 锐评**：降息预期再次被拉高，但实际行动仍取决于通胀数据。市场在博弈预期差。

### 2. 英伟达市值突破 3.5 万亿美元

**事件**：NVIDIA 发布新一代 Blackwell Ultra GPU，市值单日增加 2000 亿美元。
**影响**：AI 算力军备赛再升级，拉动半导体板块整体上涨。

**🦞 Claw 锐评**：英伟达的估值已经 price-in 了未来两年的增长。关注其数据中心收入是否能在 Q2 维持 200% 以上增速。

### 3. 中国央行意外降准 50bp

**事件**：中国人民银行宣布全面降准 0.5 个百分点，释放约 1 万亿元流动性。
**影响**：离岸人民币短线走弱，A50 期货跳涨。
**数据**：降准后 DR007 预计回落至 1.6% 以下。

## 二、投资信号与策略

- **当前阶段**：全球流动性宽松期，风险偏好回升
- **避免**：追高科技股短期涨幅，等待回调布局
- **避免**：忽视地缘政治风险对供应链的冲击
- **关注**：降息周期下的黄金和 REITs 配置机会
- **关注**：中国政策宽松对港股估值修复的催化作用

## 三、风险提示

- 本周五美国 PCE 数据若超预期，可能引发鹰派预期反弹
- 中东局势升级可能推高油价，冲击通胀预期
- 中国地产行业仍在寻底，信用风险不容忽视
"""

MOCK_OCR_WEEKLY = """\
## 📌 核心判断

> 本周文档 AI / OCR 领域核心看点：端到端文档理解模型性能全面逼近商用方案，版面分析开源工具迎来 YOLO 架构革命。

## 一、本周核心结论

### 1. 端到端 OCR 迈入商用对抗期

**结论**：GOT-OCR2.0 在标准基准上全面超越 Tesseract、PaddleOCR 等开源方案，在 SROIE 和 FUNSD 数据集上接近 Azure Document Intelligence。
**依据**：GOT-OCR2.0 端到端 F1 score 达到 92.3%（SROIE），较 PaddleOCR v4 提升 8.7 个百分点。
**约束**：在复杂金融报表和多语言混排场景中仍有 5-10% 的差距。

**🦞 Claw 锐评**：开源 OCR 的追赶速度惊人。中小企业可以开始评估从商用 API 迁移到自部署方案的可行性。

### 2. 版面分析进入实时推理时代

**结论**：DocLayout-YOLO 将版面分析推理速度提升至 200fps，比传统方案快 3-5 倍，同时保持了 95%+ 的检测精度。
**依据**：基于 YOLO11 架构改造，在 PubLayNet 测试集 mAP 达到 96.1%。
**约束**：对非标准版面（如古籍、手写笔记）的泛化能力仍需验证。

### 3. 多模态文档理解成为新方向

**结论**：从传统 OCR（纯文字识别）到文档理解（结构化信息抽取），技术范式正在转移。
**依据**：Florence-2、Qwen2-VL 等 VLM 在文档 QA 任务上的表现已超过专用 OCR 管线。
**约束**：VLM 方案的推理成本仍然是专用模型的 10-50 倍。

## 二、重点事件

### 1. GOT-OCR2.0 正式开源

**事件**：浙大 & 中科院联合开源 GOT-OCR2.0 端到端文档理解模型。
**数据**：GitHub star 突破 5,000，开源首周下载量达 12,000 次。
**影响**：开源 OCR 首次在端到端指标上与商用 API 形成竞争力。

**🦞 Claw 锐评**：这是开源 OCR 社区的「GPT 时刻」。建议所有文档 AI 团队立即进行基准对比测试。

### 2. DocLayout-YOLO 发布 v1.0

**事件**：OpenDataLab 发布基于 YOLO 架构的文档版面分析工具。
**数据**：推理速度 200fps（A100），模型大小仅 15MB。
**影响**：版面分析从离线批处理进入实时在线处理时代。

### 3. Adobe Acrobat 集成 AI 文档助手

**事件**：Adobe 在 Acrobat 中内置 AI 文档理解功能，支持跨文档问答。
**影响**：商用文档 AI 产品开始从「工具」转向「助手」形态。

## 三、开源项目推荐

### 1. GOT-OCR2.0

**类型**：端到端文档理解模型
**亮点**：单模型覆盖场景文字、印刷体、手写体、数学公式
**适用场景**：发票识别、合同抽取、学术论文解析
**部署要求**：8GB+ VRAM，支持 TensorRT 加速

### 2. DocLayout-YOLO

**类型**：文档版面分析
**亮点**：YOLO 架构、实时推理、轻量级部署
**适用场景**：PDF 解析前处理、数字化档案、出版排版检测
**部署要求**：4GB+ VRAM，支持 ONNX/TensorRT

### 3. Surya

**类型**：多语言 OCR + 版面分析
**亮点**：支持 90+ 语言，开箱即用
**适用场景**：多语言文档处理、跨国企业文档数字化

## 四、趋势分析

- **OCR → 文档理解**：纯 OCR 正在被集成到更大的文档理解管线中
- **VLM 降维打击传统方案**：通用视觉语言模型在文档任务上逐步取代专用模型
- **端侧部署成为刚需**：隐私合规要求推动 OCR 从云端 API 向本地部署迁移
- **多模态训练数据稀缺**：高质量文档标注数据仍是行业瓶颈

## 五、技术趋势策略

- **当前阶段**：技术换代期，开源方案正在迅速收窄与商用的差距
- **避免**：继续依赖 Tesseract 等传统 OCR 引擎，技术代差已经明显
- **避免**：过度投入纯 OCR 管线建设，应转向端到端文档理解方案
- **关注**：GOT-OCR2.0 和 Florence-2 在自身业务场景中的适配效果
- **关注**：文档 AI 与 RAG 系统的深度整合机会
"""


_render_counter = 0


def render_report(preset_name: str, mock_markdown: str, label: str) -> Path:
    """Render a mock report and return the HTML path."""
    global _render_counter
    _render_counter += 1
    preset = get_preset(preset_name)
    draft = ReportDraft(
        markdown=mock_markdown,
        issue_label=f"Test{_render_counter}-{datetime.now().strftime('%Y%m%d')}",
        word_count=len(mock_markdown),
    )

    renderer = Jinja2Renderer(
        template_dir=ROOT / "templates",
        static_dir=ROOT / "static",
        output_dir=OUTPUT,
    )

    stats = {"信源": "12", "精选": "8", "字数": str(draft.word_count)}

    result = renderer.render(
        draft=draft,
        preset=preset,
        time_range="2026-03-10 ~ 2026-03-17",
        stats=stats,
        brand={
            "full_name": "ClawCat Brief",
            "tagline": "AI-Powered Report Engine",
            "author": "by llx & Luna",
        },
        citation_sources=["GitHub", "arXiv", "HackerNews", "Reuters"],
    )
    print(f"  [{label}] HTML: {result['html_path']}")
    return Path(result["html_path"])


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    print("=" * 60)
    print("End-to-End Rendering Test (DaisyUI + Tailwind)")
    print("=" * 60)
    print()

    paths = []
    paths.append(render_report("ai_cv_weekly", MOCK_AI_WEEKLY, "AI 周报"))
    paths.append(render_report("ai_cv_weekly", MOCK_OCR_WEEKLY, "OCR 周报"))
    paths.append(render_report("finance_daily", MOCK_FINANCE_DAILY, "金融日报"))

    print()
    print("=" * 60)
    print(f"All {len(paths)} reports rendered successfully")
    print(f"Output directory: {OUTPUT}")
    print("=" * 60)
    for p in paths:
        print(f"  -> {p.name}")


if __name__ == "__main__":
    main()
