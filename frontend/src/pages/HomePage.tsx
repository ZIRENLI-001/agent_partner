import { Button } from "antd";
import {
  ArrowRight,
  ClipboardList,
  FileSearch,
  GitBranch,
  LineChart,
  ShieldCheck,
  Zap
} from "lucide-react";
import { Link } from "react-router-dom";

const capabilities = [
  {
    title: "指令解析",
    description: "目标、流程、FAQ、异常分支结构化。",
    icon: FileSearch
  },
  {
    title: "用户模拟",
    description: "覆盖拒绝、追问、退出、超范围分支。",
    icon: GitBranch
  },
  {
    title: "证据报告",
    description: "Rubric、得分、失败原因、证据链。",
    icon: ShieldCheck
  }
];

const workflowSteps = [
  { code: "01", title: "模型配置" },
  { code: "02", title: "样本导入" },
  { code: "03", title: "指令解析" },
  { code: "04", title: "Rubric" },
  { code: "05", title: "对话模拟" },
  { code: "06", title: "执行评测" },
  { code: "07", title: "报告分析" }
];

const modes = [
  {
    title: "端到端快速评测",
    description: "一次输入，自动生成完整报告。",
    tags: ["快速评测", "快速验收", "证据链"],
    to: "/quick-evaluation",
    icon: Zap
  },
  {
    title: "分阶段评测",
    description: "逐步校准解析、Rubric、场景与结果。",
    tags: ["专家调试", "规则校准", "可重跑"],
    to: "/evaluation",
    icon: GitBranch
  },
  {
    title: "评测历史",
    description: "复看历史报告与量化指标。",
    tags: ["复看报告", "打开明细", "追溯结果"],
    to: "/history",
    icon: ClipboardList
  }
];

export function HomePage() {
  return (
    <section className="home-dashboard compact-home">
      <div className="home-hero">
        <section className="home-hero-main">
          <span className="section-kicker">Evaluation Console</span>
          <h1>复杂指令分阶段评测流程</h1>
          <p>
            面向美团履约数字人外呼场景，将模型配置、样本导入、指令解析、
            Rubric、对话模拟、执行评测和报告分析串成可追溯的评测链路。
            支持端到端自动评测和分阶段评测，评测记录按项目隔离保存。
          </p>
          <div className="button-row">
            <Link to="/quick-evaluation">
              <Button type="primary" icon={<ArrowRight size={16} />}>
                开始端到端快速评测
              </Button>
            </Link>
            <Link to="/evaluation">
              <Button>进入分阶段评测</Button>
            </Link>
            <Link to="/history">
              <Button>查看历史评测</Button>
            </Link>
          </div>
        </section>

        <div className="home-capability-grid">
          {capabilities.map((item) => {
            const Icon = item.icon;
            return (
              <article className="home-capability-card" key={item.title}>
                <span className="capability-icon">
                  <Icon size={21} />
                </span>
                <div>
                  <h2>{item.title}</h2>
                  <p>{item.description}</p>
                </div>
              </article>
            );
          })}
        </div>
      </div>

      <div className="workflow-strip" aria-label="评测流程">
        {workflowSteps.map((step) => (
          <div className="workflow-step" key={step.code}>
            <span>{step.code}</span>
            <strong>{step.title}</strong>
          </div>
        ))}
      </div>

      <div className="mode-grid">
        {modes.map((mode) => {
          const Icon = mode.icon;
          return (
            <Link className="mode-card" to={mode.to} key={mode.title}>
              <span className="mode-card-icon">
                <Icon size={22} />
              </span>
              <div>
                <strong>{mode.title}</strong>
                <span>{mode.description}</span>
              </div>
              <div className="tag-row">
                {mode.tags.map((tag) => (
                  <em key={tag}>{tag}</em>
                ))}
              </div>
              <Button block>
                {mode.title === "评测历史"
                  ? "查看历史记录"
                  : mode.title === "分阶段评测"
                    ? "进入分阶段评测"
                    : "开始快速评测"}
              </Button>
            </Link>
          );
        })}
      </div>

      <div className="home-footer-strip">
        <span>
          <ClipboardList size={17} />
          评测过程可解释
        </span>
        <span>
          <LineChart size={17} />
          评测结果可量化
        </span>
        <span>
          <ShieldCheck size={17} />
          一站式自动评估
        </span>
      </div>
    </section>
  );
}
