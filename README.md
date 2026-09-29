# 抽水试验降深复核应用（Theis 模型）

首版范围：**均质、各向同性、等厚、无限延伸的承压含水层；完整井；恒定流量；
单一观测井**。使用 SciPy 对 Theis (1935) 解析解做非线性最小二乘拟合，
React + Plotly.js 展示降深曲线与残差，PostgreSQL 保存井距、抽水量、
观测时间和参数边界。

> 仅用于参数解释与曲线复核，**不输出任何开采/取水许可结论**；
> 假设不满足时界面和 API 都会给出中文局限提示。

## 目录

```
backend/        FastAPI + SciPy + SQLAlchemy（PostgreSQL / SQLite 兼容）
  app/theis.py       Theis 井函数 exp1、curve_fit、残差与适用性检查
  app/units.py       距离 / 流量 / 时间单位 -> SI
  app/database.py    analyses 表：一次保存一行（input_json + result_json）
  app/routers/       /api/fit /api/analyses /api/analyses/{id}/refit /api/demo
  tests/             12 项核对测试
frontend/       React 18 + Vite + Plotly.js（basic dist）
docker-compose.yml   一键启动 PostgreSQL 16 + API
```

## 快速开始（无 Docker 时用 SQLite 本地跑）

后端：

```bash
cd backend
pip install -r requirements.txt          # 或 python -m pip install --user ...
python -m pytest tests/ -q               # 运行全部核对测试
python -m uvicorn app.main:app --reload  # http://localhost:8000/docs
```

前端：

```bash
cd frontend
npm install
npm run dev                               # http://localhost:5173
```

生产形态用 PostgreSQL：

```bash
export DATABASE_URL='postgresql+psycopg2://theis:theis_local_pw@localhost:5432/theis'
docker compose up --build                 # 或自建 PG 后只启动 api
cd frontend && npm run build             # dist/ 会被 FastAPI 直接托管
```

## 模型与单位

`s(r,t) = Q/(4πT) · W(u)`，`u = r²S/(4Tt)`，`W(u) = E₁(u)`（`scipy.special.exp1`）。

内部统一 SI（m、s、m³/s、m²/s）。界面可选距离 m/cm/ft、流量
m³/s、m³/min、m³/h、L/s、gpm、时间 s/min/h/d；降深固定以 **m** 输入，
基准必须是抽水前稳定水位。拟合在 log(T)、log(S) 空间加边界，
默认对数空间加权（早晚期等权），可切换线性加权；初值取 Cooper-Jacob 晚期直线。

## 数据导入与缺测

- 粘贴两列文本 `时间,降深`（逗号/分号/Tab/空格分隔，可含表头）；
- **缺测行留空或写 null，保持缺失**：不参与拟合、不插补，逐点结果中对应字段
  仍为 null，并提示缺测数量；
- 负降深（恢复阶段/基准错误）直接拒绝并提示检查基准水位。

## 结果与重现

保存为 `analyses` 表中的**一行**：`input_json` 是完整输入快照（单位、井距、
流量、边界、含 null 的原始序列），`result_json` 为参数、95% CI、逐点残差、
告警与局限。`POST /api/analyses/{id}/refit` 仅用该快照重算并在服务端校验
T、S 与保存值一致，实现“一次保存的输入可重现”。

## 三类内置核对案例（界面一键载入）

| 案例 | 真实参数 | 预期 |
|---|---|---|
| 合成已知参数 | T=5e-3 m²/s, S=2e-4 | T、S 回收误差 <2%/5%，R²>0.999，无告警 |
| 含 1 cm 噪声 + 2 缺测 | 同上 | T 误差 <5%，缺测点保持 null，提示缺测数 |
| 井距单位错误（100 m 误标 ft） | 同上 | 拟合 R² 仍 >0.999，但 S 被高估 1/(0.3048)²≈10.76 倍；界面恒显 r²–S 耦合警示；标成 cm 这类量级错误会触发 S 越界/贴边告警 |

单观测井无法从曲线本身识别井距单位错误（S 与 r² **成反比**耦合），
因此井距必须现场独立核对——该说明随每次结果返回。

## 主要适用性告警

S/T 越出常见范围、拟合值贴搜索边界、残差对 ln(t) 有系统趋势（边界/越流/
潜水迟后疏干迹象）、观测跨度不足一个数量级、首点已有明显降深（基准存疑）、
降深频繁回落（混入恢复数据）。
