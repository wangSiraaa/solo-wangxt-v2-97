# 抽水试验降深曲线复核应用（首版）

面向水文团队复核抽水试验降深曲线的分析应用。采用**明确的简化模型**——
Theis (1935) 解，限定：

- 均质、各向同性、等厚、**承压**含水层；
- 抽水井完整、**恒定流量** Q；
- **一个观测井**，井距 r；
- 无越流、无定水/隔水边界、无井储与表皮效应（Theis 基本假设）。

> 本工具仅用于室内复核与教学核对，**不输出真实开采许可**，也不构成任何行政结论。
> 当数据不满足上述假设时，结果页会列出模型局限与残差特征提示（早期井储、
> 晚期边界/越流、S 量级异常等）。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 18 + Plotly.js（Vite 构建），半对数降深曲线 + 残差图 |
| 后端 | FastAPI + SciPy（`scipy.optimize.curve_fit`，对数参数空间拟合 T、S） |
| 数据库 | PostgreSQL（井距/流量及其单位、观测时间与降深、参数边界、拟合结果） |

## 模型

```
s(t) = Q / (4πT) · W(u)
u    = r²S / (4Tt)
W(u) = E1(u)  (scipy.special.exp1)
```

内部全部换算为 SI（s、m、m³/s）。单位选择器与数值**一起**保存：单位选错是
数据问题，系统通过输入检查与参数量级诊断提示，而不是悄悄改写数据。

## 目录

```
app/
├── backend/            FastAPI 服务
│   ├── app/
│   │   ├── main.py         路由：/api/fit /api/runs /api/runs/{id}/refit /api/demo/*
│   │   ├── theis.py        Theis 公式
│   │   ├── fit.py          SciPy 拟合 + 假设诊断
│   │   ├── units.py        单位换算（s/min/h/d、m/ft、m³/s、L/s、gpm）
│   │   ├── validation.py   单位、基准水位、缺失、重复、量级检查
│   │   ├── models.py       SQLAlchemy：runs / observations（缺测存 NULL）
│   │   ├── synthetic.py    合成数据（与测试共用）
│   │   └── service.py      换算→检查→拟合→曲线/残差组装
│   └── tests/test_verification.py
├── frontend/           React + Plotly（构建产物 dist/ 由 FastAPI 直接托管）
└── scripts/            start_postgres.sh / start_backend.sh
```

## 运行

```bash
# 1) PostgreSQL（本环境为无 root 解包的官方 arm64 包；生产请用正式实例）
bash app/scripts/start_postgres.sh

# 2) 后端（首次已装 Python 依赖；自动 create_all 建表）
bash app/scripts/start_backend.sh
#   打开 http://127.0.0.1:8000/

# 前端开发模式（热更新）
cd app/frontend && npm install && npm run dev   # 5173，/api 代理到 8000
# 生产构建
cd app/frontend && npm run build                # 产物由 FastAPI 在 / 托管
```

## 使用流程

1. 录入/选择井距 r、流量 Q 及各自**单位**，选择时间与降深单位；
2. 填写抽水前静水位与基准约定（降深必须以同一静水位为基准：s = 静水位 − 实测水位）；
3. 设置 T、S 参数边界（SI），导入 CSV/TXT 或粘贴「时间 降深」两列；
   缺测行留空或写 `NA`，**保持缺失、不插补**，图中以缺口显示；
4. 点击拟合，查看：
   - 半对数降深曲线（实测点 + Theis 曲线 + 缺测位置）；
   - 残差图（实测 − 模型，零轴线）；
   - T、S、RMSE、R² 与所用边界；
   - 输入检查（单位换算、基准、缺失、重复、量级）；
   - 模型假设与局限诊断；
5. 勾选“保存本次输入”后写入 PostgreSQL，可在左侧列表读取或**用保存的原始输入
   重新拟合**以验证重现性。

## 核对结果（内置三案例，可在界面一键载入）

测试见 `backend/tests/test_verification.py`（`pytest`），合成数据真值
T = 1.2e-3 m²/s，S = 2e-4，r = 50 m，Q = 80 m³/h：

1. **合成已知参数（无噪声）**：拟合 T = 1.200000e-03、S = 2.000000e-04，
   R² = 1.00000000，RMSE < 1e-6 m；
2. **含 0.01 m 高斯噪声 + 2 个缺测**：T = 1.2005e-03（偏差 <0.1%）、
   S = 2.0029e-04，RMSE ≈ 6.5e-3 m；两个缺测在数据库中为 NULL、
   图上保留缺口、不参与拟合；
3. **距离单位错误**：真实井距 300 ft（≈91.4 m）被误录为 1500 m。
   曲线形状仍 R²≈1、T 不变（尺度错误无法由形状暴露），但 S ∝ r² 被压缩到
   7.4e-7，跨越承压含水层常见下限，系统给出 `S_TOO_LOW` 警告并提示核对
   井距/流量单位；
4. **可重现性**：保存后 GET 读取与 POST `refit`（仅用保存的原始输入重算）
   得到逐位相同的 T、S。

## 已知局限（首版）

- 单观测井、单段定流量；不支持阶梯流量、多井、水位恢复段联合分析；
- 仅承压 Theis；不适用潜水（需 Neuman）、越流（Hantush–Jacob）、
  有边界含水层及井储/表皮显著的早期数据；
- 单位错误若恰好使 S 仍落在 1e-6~1e-3 区间（如纯 ft/m 混淆），曲线与量级
  诊断可能无法识别——这是单井 Theis 反演的固有不可识别性，需靠原始记录核对；
- 诊断为辅助判断，最终参数解释由水文地质人员负责。
