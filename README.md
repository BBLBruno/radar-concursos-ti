# Radar de Concursos TI

> **PT-BR:** Pipeline automatizado de inteligência geográfica e monitoramento de editais públicos de Tecnologia da Informação em um raio de 250 km de Muzambinho (MG).  
> **EN-US:** Automated geographic intelligence and monitoring pipeline for public-sector IT job notices within a 250 km radius of Muzambinho (MG, Brazil).

**Aplicação em Produção / Live Application:** [https://radar-concursos-ti.vercel.app](https://radar-concursos-ti.vercel.app)

---

## 🇧🇷 Português (PT-BR)

### O Projeto

Acompanhar editais públicos de TI no interior de Minas Gerais e leste paulista costuma exigir triagem manual em portais nacionais que misturam milhares de cargos gerais sem filtros de proximidade ou tempo real de deslocamento.

O **Radar de Concursos TI** automatiza esse processo de ponta a ponta: um pipeline em **Python** agendado via **GitHub Actions** coleta dados públicos de **21 canais monitorados** do PCI Concursos, aplica validação e extração via **Regex** (cargos de TI e faixas salariais), cruza municípios com a base oficial do **IBGE** (`data/municipios_mg_sp.json`, 1.590 municípios em MG, SP e RJ), calcula distâncias e tempos rodoviários reais pela API **OpenRouteService** (com fallback geodésico pela fórmula de **Haversine** e cache em `data/distancias_cache.json`) e alimenta o painel analítico estático (`index.html`) hospedado na Vercel.

### Principais Recursos

- **Raio de 250 km Georreferenciado (IBGE):** Cruzamento municipal com a malha oficial do IBGE para filtrar oportunidades elegíveis em MG, SP e RJ a partir de Muzambinho - MG.
- **Roteamento Rodoviário Real (OpenRouteService + Haversine):** Cálculo de distância rodoviária e tempo estimado de viagem (`driving-car`) via OpenRouteService API, com fallback geodésico (Haversine) e persistência em cache local (`data/distancias_cache.json`).
- **Extração e Classificação via Regex:** Validação estrita de cargos de TI (`IT_CARGO_REGEX`), extração de remunerações por expressões regulares e separação automática de editais mistos por escolaridade (`Médio/Técnico` e `Superior`).
- **Painel Analítico & SLA (`index.html`):** Interface responsiva com filtros dinâmicos (escolaridade, cidade/UF, distância máxima, busca textual), sinalização visual por urgência de prazo de inscrição e lista local de favoritos (`localStorage`).

### Arquitetura e Automação

```text
[PCI Concursos (21 canais)] ──> [concursos_muzambinho.py (Regex + IBGE + ORS/Haversine)] ──> [concursos_muzambinho_ti.json] ──> [index.html (Vercel)]
```

- **Pipeline de Coleta e Dados (`concursos_muzambinho.py`):** Implementado em Python 3 utilizando exclusivamente a biblioteca padrão (`urllib`, `re`, `json`, `dataclasses`, `argparse`, `math`), evitando dependências externas pesadas.
- **Agendamento CI/CD (`.github/workflows/monitor_concursos.yml`):** Workflow do GitHub Actions configurado para executar automaticamente toda **segunda, quarta e sexta-feira às 11:25 UTC (08:25 BRT)**, além de disparo manual (`workflow_dispatch`), atualizando `concursos_muzambinho_ti.json` e `data/distancias_cache.json` no repositório.
- **Entrega Front-end (`vercel.json` + `index.html`):** Aplicação estática com Tailwind CSS e Lucide Icons servida com cabeçalhos de segurança e controle de cache otimizado para o snapshot JSON.

### Execução Local

```powershell
# Iniciar o painel analítico localmente
python -m http.server 8000

# Executar o pipeline de varredura manualmente (raio de 250 km)
python concursos_muzambinho.py --raio 250 --saida concursos_muzambinho_ti.json --force
```

---

## 🇺🇸 English (EN-US)

### Overview

Tracking public-sector IT openings across inland Minas Gerais and eastern São Paulo typically requires manual screening across national portals that mix thousands of non-IT roles without geographic radius or travel-time filtering.

**Radar de Concursos TI** automates this workflow end to end: a **Python** pipeline scheduled via **GitHub Actions** collects public notices across **21 monitored channels** on PCI Concursos, extracts and validates IT roles and salaries using **Regex**, cross-references locations against the official **IBGE** municipal dataset (`data/municipios_mg_sp.json`, 1,590 municipalities across MG, SP, and RJ), computes real driving distances and travel times via the **OpenRouteService** API (with **Haversine** geodesic fallback and local route caching in `data/distancias_cache.json`), and feeds the analytical dashboard (`index.html`) deployed on Vercel.

### Key Capabilities

- **250 km Georeferenced Radius (IBGE):** Matches public notices against IBGE municipal coordinates to filter opportunities within 250 km of Muzambinho - MG.
- **Road Routing & Geodesic Fallback (OpenRouteService + Haversine):** Computes real driving distances and travel durations (`driving-car`) via OpenRouteService API, backed by local cache (`data/distancias_cache.json`) and Haversine geodesic fallback.
- **Regex Extraction & Level Partitioning:** Applies strict IT-role validation (`IT_CARGO_REGEX`), regex-based salary parsing, and automatic partitioning of multi-role notices by education tier (`Médio/Técnico` and `Superior`).
- **Analytical Dashboard (`index.html`):** Responsive dashboard with dynamic filtering (education level, city/state, distance, search), deadline urgency indicators, and browser-persisted targets (`localStorage`).

### Architecture & Automation

- **Python Pipeline (`concursos_muzambinho.py`):** Built with Python 3 standard library modules (`urllib`, `re`, `json`, `dataclasses`, `argparse`, `math`) for deterministic, zero-dependency execution.
- **GitHub Actions Schedule (`.github/workflows/monitor_concursos.yml`):** Automated cron execution every **Monday, Wednesday, and Friday at 11:25 UTC (08:25 BRT)** plus manual `workflow_dispatch`, committing updated snapshots (`concursos_muzambinho_ti.json` and `data/distancias_cache.json`).
- **Static Deployment (`vercel.json` + `index.html`):** Static analytical front-end (Tailwind CSS & Lucide Icons) served on Vercel with security headers and JSON cache-control rules.

### Local Execution

```powershell
# Serve the analytical dashboard locally
python -m http.server 8000

# Run the collection pipeline manually (250 km radius)
python concursos_muzambinho.py --raio 250 --saida concursos_muzambinho_ti.json --force
```

---

## Tecnologias / Tech Stack

- **Pipeline & Dados / Data Pipeline:** Python 3 (`urllib`, `re`, `json`, `dataclasses`, `argparse`, `math`)
- **Geodados & Roteamento / Geodata & Routing:** Base Municipal IBGE (`data/municipios_mg_sp.json`), OpenRouteService API (`driving-car`), Haversine
- **Automação & Deploy / Automation & Hosting:** GitHub Actions (`.github/workflows/monitor_concursos.yml`) & Vercel (`vercel.json`)
- **Painel Analítico / Dashboard:** HTML5, Tailwind CSS, JavaScript (`localStorage`), Lucide Icons

---

## Autor / Author

**Bruno Bianchi Léo**  
Bacharel em Ciência da Computação • BizOps, Processos, Dados & Automação  
[LinkedIn](https://www.linkedin.com/in/bruno-bianchi-leo/) • [GitHub](https://github.com/BBLBruno) • [Live App](https://radar-concursos-ti.vercel.app)
