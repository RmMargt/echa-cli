# ECHA Chemical Data MCP Server

欧洲化学品管理局 (ECHA) 数据查询 MCP Server，提供 9 个工具覆盖物质信息、CLP 分类、REACH 注册分类和毒理数据。

## 🔧 Tools 一览

| Tool | 描述 | 数据源 | 默认限制 |
|------|------|--------|----------|
| `echa_get_substance_info` | 物质基本信息（CAS、EC、名称） | REST API | — |
| `echa_list_dossiers` | REACH 注册卷宗列表 | REST API | `max_results=10` |
| `echa_get_clp_classification` | CLP 通报分类（行业自主分类） | REST API | `max_results=5` |
| `echa_get_harmonised_classification` | 统一分类（Annex VI 官方分类） | REST API | — |
| `echa_get_reach_ghs` | REACH 卷宗 GHS 分类（Section 2.1） | HTML 解析 | — |
| `echa_get_reach_pbt` | REACH 卷宗 PBT 评估（Section 2.3） | HTML 解析 | — |
| `echa_get_toxicology_summary` | 毒理概述 + DN(M)ELs（快速） | HTML 解析 | — |
| `echa_get_toxicology_studies` | 毒理个体研究记录（可按章节过滤） | HTML 解析 | `max_studies=50` |
| `echa_get_toxicology_full` | 完整毒理数据（慢） | HTML 解析 | 内部限制 100 |

## 📚 Resources

| Resource URI | 描述 |
|---|---|
| `echa://hcode-mapping` | GHS 危害分类 → H 代码映射表（Markdown） |
| `echa://hcode-mapping-json` | H 代码映射表（JSON） |

## 🚀 Quick Start

### 安装

```bash
# pip
pip install echa-cli

# 或 uv（推荐，自动隔离环境）
uv tool install echa-cli

# 或从源码
pip install -e .
```

安装后提供两个命令：
- `echa-cli` — 命令行工具（供终端直接使用）
- `echa-mcp` — 启动 MCP Server（供 AI 助手使用）

### 方式一：CLI 命令行

无需启动服务，直接查询 ECHA 数据：

```bash
# 查询物质基本信息（CAS、EC、名称、分子式）
echa-cli substance-info 100.000.002

# 查询统一分类（Annex VI，具有法律约束力）
echa-cli harmonised 100.000.002

# 查询 CLP 行业通报分类（默认前 5 条）
echa-cli clp 100.000.002
echa-cli clp 100.000.002 --max-results 3

# 查询 REACH 注册卷宗列表
echa-cli list-dossiers 100.000.002

# 查询 REACH GHS 分类（需要 CAS 号）
echa-cli reach-ghs 100.000.002 50-00-0

# 查询 REACH PBT 评估（需要 CAS 号）
echa-cli reach-pbt 100.000.002 50-00-0

# 毒理学概述 + DNEL 值（快，10-30s）
echa-cli tox-summary 100.000.002

# 特定毒理学章节（如急性毒性 7.2）
echa-cli tox-studies 100.000.002 --section 7.2 --max-studies 10

# 完整毒理学数据（慢，可能需要数分钟）
echa-cli tox-full 100.000.002

# 查看帮助
echa-cli --help
echa-cli substance-info --help
```

所有命令输出 JSON 到 stdout，可以配合 `jq`、`python -m json.tool` 等工具处理。

### 方式二：MCP Server（供 AI 助手使用）

```bash
python -m echa_mcp.server
# 或
echa-mcp
```

服务启动后监听 `http://0.0.0.0:7082`（端点：`/mcp`，Streamable HTTP 传输）。

配置到 MCP 客户端：

```json
{
  "mcpServers": {
    "echa": {
      "url": "http://192.168.89.193:7082/mcp"
    }
  }
}
```

## 📋 示例用法与返回结果

### 1. 查询物质基本信息 — `echa_get_substance_info`

**输入:**
```json
{
  "substance_index": "100.000.002"
}
```

**返回:**
```json
{
  "substance_index": "100.000.002",
  "cas_number": "50-00-0",
  "ec_number": "200-001-8",
  "chemical_name": "Formaldehyde",
  "iupac_name": "formaldehyde",
  "molecular_formula": "CH2O",
  "inchi": "InChI=1S/CH2O/c1-2/h1H2",
  "smiles": "C=O",
  "index_number": "605-001-00-5",
  "all_cas_numbers": [
    "1053659-79-2", "8013-13-6", "1158237-02-5", "50-00-0",
    "1416946-65-0", "1227476-28-9", "1156543-56-4", "1357848-44-2",
    "8005-38-7", "8006-07-3", "1609158-91-9", "112068-71-0"
  ],
  "all_ec_names": ["Formaldehyde"],
  "all_iupac_names": ["formaldehyde"]
}
```

### 2. 查询 CLP 通报分类 — `echa_get_clp_classification`

**输入:**
```json
{
  "substance_index": "100.000.002",
  "max_results": 3
}
```

**返回（节选）:**
```json
{
  "substance_index": "100.000.002",
  "total_available": 50,
  "returned": 3,
  "truncated": true,
  "classifications": [
    {
      "notification_percentage": 34.19,
      "hazard_categories": ["Carc. 2", "Acute Tox. 3 (Inhalation)", "Skin Corr. 1B", "Skin Sens. 1"],
      "hcodes": ["H301", "H311", "H314", "H317", "H331", "H351"],
      "signal_word": "Danger"
    }
  ]
}
```

### 3. 推荐工具调用顺序

以查询甲醛 (Formaldehyde, substance_index: `100.000.002`) 为例:

1. `echa_get_substance_info` → 获取 CAS (50-00-0)、EC、名称
2. `echa_get_harmonised_classification` → 查看统一分类（Annex VI）
3. `echa_get_clp_classification` → 查看行业通报分类（默认返回前 5 条）
4. `echa_get_toxicology_summary` → 快速查看毒理概述和 DNEL 值

## 🏗 技术架构

```
echa_mcp/
├── server.py              # FastMCP 入口，注册 tools + resources
├── clients/
│   └── echa_client.py     # 异步 HTTP 客户端（httpx，绕过本地代理）
├── tools/                 # MCP tool 实现
│   ├── substance.py       # 物质信息 + 卷宗列表
│   ├── clp_classification.py
│   ├── harmonised_classification.py
│   ├── reach_classification.py
│   └── toxicology.py
├── parsers/               # HTML 解析器（兼容 ECHA 新版 UUID 文档链接）
│   ├── common.py          # 共享解析工具
│   ├── section2_parser.py # Section 2 GHS/PBT
│   └── section7_parser.py # Section 7 毒理
├── models/                # Pydantic 输入模型
│   ├── substance.py
│   ├── classification.py
│   └── toxicology.py
└── data/
    └── hcode_mapping.py   # H-code 映射表
```

## ⚠️ 注意事项

- **代理绕过**：httpx 客户端已配置 `proxy=None`，绕过本地代理（ClashX 等）。ECHA 的 HTML dossier 页面（~1MB）通过代理下载时会断连。
- **超时设置**：连接超时 30s / 读取超时 120s，适配从中国直连 ECHA 服务器的延迟。
- **结果限制**：CLP 分类默认返回前 5 条、卷宗默认 10 条、研究默认 50 条。可通过 `max_results` / `max_studies` 参数调整。
- **HTML 解析**：依赖 ECHA dossier HTML 页面结构（2025 年起使用 UUID 格式文档链接），如 ECHA 修改前端结构可能需要更新解析器。

## 依赖

- `mcp[cli]` >= 1.0.0 (MCP Python SDK)
- `httpx` >= 0.27.0 (异步 HTTP)
- `beautifulsoup4` >= 4.12.0 (HTML 解析)
- `pydantic` >= 2.0.0 (输入验证)
- `typer` >= 0.9.0 (CLI 框架)
