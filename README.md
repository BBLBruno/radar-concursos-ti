# Radar de Concursos TI — Inteligência Geoespacial e Monitoramento de Editais

Sistema automatizado de coleta, qualificação estrutural, roteamento geoespacial e visualização analítica de editais públicos de **Tecnologia da Informação e Computação** (Níveis Médio, Técnico e Superior) em um raio de **250 km a partir de Muzambinho - MG**.

Desenvolvido com arquitetura orientada a dados (*Data-Driven Static Architecture*), zero dependências pesadas no front-end e pronto para deploy contínuo na **Vercel** integrado ao **GitHub Actions**.

---

## Arquitetura e Engenharia do Sistema

### 1. Pipeline de Coleta e Qualificação (`concursos_muzambinho.py`)
- **Monitoramento Multicanal (21 Fontes)**: Varredura automatizada nas listagens regionais (`Sudeste`, `Nacional`) e em 19 canais específicos de cargos de TI (`Técnico em Informática`, `Técnico de Informática`, `Técnico em TI`, `Suporte Técnico`, `Técnico de Suporte`, `Assistente de TI`, `Auxiliar de Informática`, `Operador de Computador`, `Tecnologia da Informação`, `Informática`, `Analista de Sistemas`, `Analista de TI`, `Computação`, `Programador`, `Redes`, `Suporte`, `Ciência da Computação`, `Engenharia da Computação` e `Professor de Informática`).
- **Inspeção Estrutural de Editais (`<article>`)**: O coletor acessa a página individual de cada certame, analisa a árvore de cargos (`<li>` e cabeçalhos de seção de escolaridade) e valida os cargos estritamente contra expressões regulares de TI (`IT_CARGO_REGEX` e `EXCLUDE_CARGO_REGEX`), eliminando falsos positivos de editais gerais.
- **Separação Automática em Blocos por Nível (`Médio/Técnico` vs. `Superior`)**: Quando um mesmo edital geral oferece vagas de TI tanto para nível Médio/Técnico quanto para nível Superior (ex.: *TRF3*, *SETEC Campinas*, *Prefeitura de Taquaritinga*), o pipeline divide os cargos em blocos independentes (`-mt` e `-sup`), atribuindo a cada bloco exclusivamente seus cargos, níveis e faixa salarial correspondente, sem duplicatas.
- **Extração de Links Diretos das Bancas**: Identifica o link oficial da banca organizadora dentro do edital e resolve automaticamente a URL direta do concurso nos portais compatíveis (ex.: `selecao.net.br`, portais de admissão universitária e comandos militares), mantendo o link da página oficial da banca e o link direto do edital no PCI Concursos.
- **Política de Dados 100% Verificados (Zero Dados Inventados ou Estáticos)**:
  - **Salários**: Extraídos por Regex diretamente do bloco ou cabeçalho do cargo (`salario_num` e `salario_formatado`). Quando o edital informa apenas valor por hora-aula ou omite a remuneração, o sistema registra explicitamente `"Indisponível"` (ou o valor nominal por hora-aula) sem estimar salários mensais fictícios.
  - **Distância e Tempo de Condução (`OpenRouteService`)**: Quando a variável `OPENROUTESERVICE_API_KEY` está configurada, calcula a distância rodoviária exata (`driving-car`) e o tempo real de viagem a partir de Muzambinho - MG. Na ausência da chave, exibe exclusivamente a distância geodésica oficial calculada sobre a malha do IBGE (`distancia_reta_km`) e define o tempo de condução como `"Indisponível"`, sem aplicar fatores multiplicadores artificiais.

### 2. Interface Analítica (`index.html`)
- **Design Analítico de Alta Densidade**: Interface limpa, sem emojis, projetada com foco em legibilidade, contraste tipográfico (`Inter` + `JetBrains Mono` com `tabular-nums`) e tomada de decisão rápida.
- **KPIs 100% Dinâmicos**: Indicadores de topo calculados em tempo real sobre o conjunto filtrado (Total de Blocos/Editais, Cidades Mapeadas, Maior Remuneração e Menor Distância).
- **SLA de Prazo de Inscrição por Cores**:
  - **Vermelho Pulsante (`Urgente • Xd` / `Encerra hoje`)**: 5 dias ou menos restantes.
  - **Âmbar (`Atenção • X dias`)**: De 6 a 15 dias restantes.
  - **Esmeralda (`X dias`)**: Mais de 15 dias restantes (exibe apenas a contagem de dias e a cor, sem rótulos supérfluos).
  - **Cinza (`Indisponível`)**: Quando a data limite não foi divulgada no extrato.
- **Controles de Filtragem e Persistência**:
  - Ordem de escolaridade orientada do nível inicial ao avançado: `Médio` > `Técnico` > `Superior`.
  - Filtro de áreas de atuação (`Todas`, `Infraestrutura e Redes`, `Programação e Sistemas`, `Dados e IA`), UF (`MG`, `SP`), busca textual, slider de salário mínimo e ordenação matemática.
  - Gestão de **Meus Alvos** persistida via `localStorage`.

---

## Estrutura de Arquivos

```text
Agente - Concurso/
├── index.html                   # Interface analítica client-side (Tailwind CSS)
├── vercel.json                  # Configuração de deploy estático e cabeçalhos de cache
├── concursos_muzambinho.py      # Pipeline Python de coleta, parsing estrutural e rotas
├── concursos_muzambinho_ti.json # Base JSON gerada com metadados e blocos de editais
├── abrir_dashboard.bat          # Inicializador rápido do servidor HTTP local (porta 8000)
├── data/
│   ├── municipios_mg_sp.json    # Malha oficial IBGE (1.590 municípios com coordenadas)
│   └── distancias_cache.json    # Cache persistente de rotas consultadas na API ORS
├── agendar_tarefa_windows.bat   # Atalho de agendamento no Windows Task Scheduler
├── agendar_tarefa_windows.ps1   # Script PowerShell de agendamento (Seg, Qua, Sex às 08:00)
├── remover_tarefa_windows.bat   # Remoção da tarefa agendada no Windows
└── .github/workflows/
    └── monitor_concursos.yml    # Pipeline CI/CD (GitHub Actions: Seg, Qua, Sex às 08:00 BRT)
```

---

## Execução Local

### 1. Visualizar o Dashboard
Execute o atalho [`abrir_dashboard.bat`](file:///c:/Users/Bruno/Projects/Agente%20-%20Concurso/abrir_dashboard.bat) ou inicie o servidor HTTP nativo do Python no terminal:

```powershell
python -m http.server 8000
```

Em seguida, acesse `http://localhost:8000` no navegador.

### 2. Executar o Coletor de Editais
```powershell
# Execução padrão (raio de 250 km):
python concursos_muzambinho.py --raio 250

# Execução com chave da API OpenRouteService:
$env:OPENROUTESERVICE_API_KEY="SUA_CHAVE_AQUI"
python concursos_muzambinho.py --raio 250
```

---

## Deploy Contínuo na Vercel + GitHub Actions

1. Publique este repositório no seu **GitHub** ([github.com/BBLBruno](https://github.com/BBLBruno)).
2. Em **Settings > Secrets and variables > Actions** no GitHub, adicione (opcionalmente) o segredo `OPENROUTESERVICE_API_KEY` com sua chave gratuita do OpenRouteService.
3. Conecte o repositório à **Vercel** ([vercel.com](https://vercel.com)). O arquivo [`vercel.json`](file:///c:/Users/Bruno/Projects/Agente%20-%20Concurso/vercel.json) já configura o roteamento estático e políticas de cache para `concursos_muzambinho_ti.json`.
4. Toda segunda, quarta e sexta-feira às 08:00 BRT, o workflow [`.github/workflows/monitor_concursos.yml`](file:///c:/Users/Bruno/Projects/Agente%20-%20Concurso/.github/workflows/monitor_concursos.yml) executa a varredura, atualiza o JSON no repositório e aciona automaticamente um novo deploy na Vercel.

---

## Autor

**Bruno Bianchi Leo**
- **Formação**: Bacharel em Ciência da Computação
- **Áreas de Atuação**: Engenharia de Automação, AI Ops, RevOps & Produto
- **LinkedIn**: [linkedin.com/in/bruno-bianchi-leo](https://www.linkedin.com/in/bruno-bianchi-leo)
- **GitHub**: [github.com/BBLBruno](https://github.com/BBLBruno)

