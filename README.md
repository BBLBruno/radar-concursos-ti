# Radar de Concursos TI

> Monitoramento automatizado de editais públicos de Tecnologia da Informação num raio de 250 km de Muzambinho (MG/SP).

**Aplicação em Produção:** [radar-concursos-ti.vercel.app](https://radar-concursos-ti.vercel.app/)

---

## O Projeto

Acompanhar concursos de TI no interior de Minas Gerais e leste paulista costuma ser um processo demorado: os portais nacionais misturam milhares de vagas gerais e não oferecem filtros de proximidade física ou tempo de viagem.

O **Radar de Concursos TI** resolve esse gargalo. O sistema coleta certames públicos continuamente, filtra exclusivamente oportunidades de Computação e Informática (Médio, Técnico e Superior), calcula distâncias e tempos de condução rodoviária a partir de Muzambinho e entrega os dados consolidados em um painel analítico com filtros dinâmicos.

---

## Principais Recursos

- **Raio de 250 km Georreferenciado:** Cruzamento com a malha oficial do IBGE para mapear polos em MG e SP.
- **Roteamento Rodoviário Real:** Distância e tempo de viagem calculados via OpenRouteService API (`driving-car`), com fallback geodésico oficial (fórmula de Haversine).
- **Separação por Escolaridade:** Editais com vagas conjuntas são particionados em blocos próprios (Médio/Técnico e Superior), exibindo apenas os cargos e salários correspondentes.
- **Extração de Salários e SLA:** Leitura de remuneração por expressões regulares e sinalização visual por urgência no encerramento das inscrições.
- **Meus Alvos:** Sistema de favoritos persistido localmente no navegador (`localStorage`).
- **Design Focado em Legibilidade:** Interface rápida e responsiva construída com Tailwind CSS, sem emojis e com tipografia técnica para desktop e mobile.

---

## Arquitetura

O sistema foi desenhado para operar com estabilidade e custo zero de infraestrutura:

```text
[PCI Concursos] ──> [Python Scraper] ──> [GitHub Actions Cron] ──> [Vercel CDN] ──> [Dashboard]
```

- **Pipeline (Python 3):** Coleta, parsing estrutural de cargos de TI, validação contra falsos positivos e cálculo de rotas usando a biblioteca padrão do Python.
- **Automação (GitHub Actions):** Varredura programada para rodar toda **segunda, quarta e sexta-feira às 08:00 BRT**, atualizando a base JSON do repositório.
- **Front-end & Deploy (Vercel):** Aplicação estática servida em rede de borda com cabeçalhos de segurança e cache otimizado.

---

## Execução Local

```powershell
# Iniciar o painel localmente:
python -m http.server 8000

# Executar a varredura manualmente:
python concursos_muzambinho.py --raio 250
```

---

## Tecnologias

- **Backend & Coleta:** Python 3 (`urllib`, `re`, `json`, `dataclasses`)
- **Geodados:** OpenRouteService API e Malha Municipal IBGE
- **Front-end:** HTML5, Tailwind CSS e Lucide Icons
- **CI/CD & Hospedagem:** GitHub Actions e Vercel Edge Network

---

## Autor

**Bruno Bianchi Leo**  
Bacharel em Ciência da Computação • Engenharia de Automação, AI Ops, RevOps e Produto  
[LinkedIn](https://www.linkedin.com/in/bruno-bianchi-leo) • [GitHub](https://github.com/BBLBruno)
