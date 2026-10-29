"""
Radar de Concursos TI - Região de Muzambinho e Raio de até 250km
Engenharia de Software, AI Ops & Product Analytics
Fontes: PCI Concursos Sudeste, Nacional e Canais Especializados de TI (Médio, Técnico e Superior)
Cálculo: OpenRouteService (Driving-Car) ou Distância Geodésica Oficial IBGE (Haversine) sem dados inventados
"""

import argparse
import csv
import io
import json
import logging
import math
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("RadarConcursosTI")

# Coordenadas oficiais de Muzambinho - MG (IBGE)
MUZAMBINHO_LAT = -21.3708
MUZAMBINHO_LON = -46.5264

# Canais oficiais de varredura no PCI Concursos (Médio, Técnico e Superior)
FONTES_CONCURSOS = [
    ("https://www.pciconcursos.com.br/concursos/sudeste/", "Sudeste"),
    ("https://www.pciconcursos.com.br/concursos/nacional/", "Nacional"),
    ("https://www.pciconcursos.com.br/vagas/tecnico-em-informatica", "Técnico em Informática"),
    ("https://www.pciconcursos.com.br/vagas/tecnico-de-informatica", "Técnico de Informática"),
    ("https://www.pciconcursos.com.br/vagas/tecnico-em-tecnologia-da-informacao", "Técnico em TI"),
    ("https://www.pciconcursos.com.br/vagas/suporte-tecnico", "Suporte Técnico"),
    ("https://www.pciconcursos.com.br/vagas/tecnico-de-suporte", "Técnico de Suporte"),
    ("https://www.pciconcursos.com.br/vagas/assistente-de-ti", "Assistente de TI"),
    ("https://www.pciconcursos.com.br/vagas/auxiliar-de-informatica", "Auxiliar de Informática"),
    ("https://www.pciconcursos.com.br/vagas/operador-de-computador", "Operador de Computador"),
    ("https://www.pciconcursos.com.br/vagas/tecnologia-da-informacao", "Tecnologia da Informação"),
    ("https://www.pciconcursos.com.br/vagas/informatica", "Informática"),
    ("https://www.pciconcursos.com.br/vagas/analista-de-sistemas", "Analista de Sistemas"),
    ("https://www.pciconcursos.com.br/vagas/analista-de-ti", "Analista de TI"),
    ("https://www.pciconcursos.com.br/vagas/computacao", "Computação"),
    ("https://www.pciconcursos.com.br/vagas/programador", "Programador"),
    ("https://www.pciconcursos.com.br/vagas/redes", "Redes"),
    ("https://www.pciconcursos.com.br/vagas/suporte", "Suporte"),
    ("https://www.pciconcursos.com.br/vagas/ciencia-da-computacao", "Ciência da Computação"),
    ("https://www.pciconcursos.com.br/vagas/engenharia-da-computacao", "Engenharia da Computação"),
    ("https://www.pciconcursos.com.br/vagas/professor-de-informatica", "Professor de Informática"),
]

# Expressão regular estrita para validação de cargos reais de TI / Computação
IT_CARGO_REGEX = re.compile(
    r"\b("
    r"informatica|computacao|ciencia da computacao|engenharia da computacao|engenharia de computacao|"
    r"engenharia de software|sistemas de informacao|sistemas da computacao|analise de sistemas|"
    r"analista de sistemas|analista de ti|analista de t i|analista de tecnologia|"
    r"tecnologia da informacao|tecnico em ti|tecnico de ti|assistente de ti|auxiliar de ti|"
    r"suporte tecnico|suporte em tecnologia|redes de computadores|arquitetura de computadores|"
    r"banco de dados|ciencia de dados|ciencias de dados|cientista de dados|analista de dados|"
    r"aprendizado de maquina|aprendizado profundo|inteligencia artificial|seguranca da informacao|"
    r"desenvolvimento de sistemas|desenvolvimento web|cloud computing|programacao|programador|"
    r"desenvolvedor|operador de computador|operador de microcomputador|processamento de dados|"
    r"analista previdenciario ti|analista tecnico informatica|monitor de informatica|instrutor de informatica"
    r")\b"
)

# Exclusão de falsos positivos administrativos ou fora de TI
EXCLUDE_CARGO_REGEX = re.compile(
    r"\b("
    r"suporte administrativo|suporte funerario|apoio administrativo|agente administrativo|"
    r"assistente administrativo|auxiliar administrativo|oficial administrativo|servicos administrativos|"
    r"analista administrativo|analista de financas|analista contabil|analista de comunicacao|"
    r"analista de compras|analista de licitacao|analista de controle interno|analista de recursos humanos"
    r")\b"
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("ASCII")
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def formatar_moeda_br(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")


def extrair_salario_bloco(
    paragrafos_artigo: List[str],
    desc_card: str,
    bloco_tipo: str,
    cargos_bloco: List[str]
) -> Tuple[Optional[float], str]:
    """
    Extrai a remuneração real a partir dos parágrafos do edital sem inventar valores.
    Ignora taxas de inscrição e auxílios/vales isolados.
    Caso haja valor específico para o cargo/nível (ex: Técnico Judiciário vs Analista Judiciário),
    extrai o valor exato daquele bloco. Caso não exista informação salarial, retorna (None, 'Indisponível').
    """
    padrao_moeda = r"R\$\s*([\d\.]+(?:,\d{2})?)"

    # 1. Filtrar sentenças que tratam de salário/remuneração/vencimento (excluindo taxas de inscrição)
    sentencas_salariais = []
    for p in paragrafos_artigo:
        for s in re.split(r"(?<=[.!?])\s+", p):
            s_norm = normalize_text(s)
            if "r$" not in s.lower():
                continue
            if any(t in s_norm for t in ["taxa de inscricao", "taxas de inscricao", "taxa varia", "taxa e de", "taxas sao de", "taxa no valor"]):
                continue
            if any(t in s_norm for t in ["remunerac", "vencimento", "salario", "bolsa", "subs", "hora", "aula", "inicial", "mensal"]):
                sentencas_salariais.append(s)

    # 2. Verificar se alguma sentença salarial especifica o valor para este bloco/cargo
    cargos_norm = " ".join(normalize_text(c) for c in cargos_bloco)
    for s in sentencas_salariais:
        s_norm = normalize_text(s)
        # Caso específico: Técnico Judiciário vs Analista Judiciário
        if bloco_tipo == "MEDIO_TECNICO" and "tecnico judiciario" in cargos_norm and "tecnico judiciario" in s_norm:
            m = re.search(padrao_moeda, s)
            if m:
                val = float(m.group(1).replace(".", "").replace(",", "."))
                return round(val, 2), formatar_moeda_br(val)
        if bloco_tipo == "SUPERIOR" and "analista judiciario" in cargos_norm and "analista judiciario" in s_norm:
            m = re.search(padrao_moeda, s)
            if m:
                val = float(m.group(1).replace(".", "").replace(",", "."))
                return round(val, 2), formatar_moeda_br(val)

        # Caso específico: Professor / PEB II remunerado por hora-aula
        if ("peb ii" in cargos_norm or "professor adjunto" in cargos_norm) and ("peb ii" in s_norm or "demais cargos de nivel superior" in s_norm):
            m_hora = re.search(r"R\$\s*([\d\.]+(?:,\d{2})?)\s*por\s*(?:hora(?:-aula)?|aula)", s, re.IGNORECASE)
            if m_hora:
                val_h = float(m_hora.group(1).replace(".", "").replace(",", "."))
                return None, f"R$ {m_hora.group(1)}/hora-aula"

    # 3. Extrair valores mensais válidos (>= R$ 600,00) das sentenças salariais (removendo trechos de vale-alimentação/cesta)
    valores_mensais = []
    eh_faixa = False
    for s in sentencas_salariais:
        # Remover menções a vale-alimentação/refeição/auxílio/cesta para não confundir com salário base
        s_sem_beneficios = re.sub(
            r"(?:somada ao |incluindo |acrescidos? de |mais |alem de |tem |terao direito a )?"
            r"(?:vale[- ]alimenta[cç][aã]o|aux[ií]lio[- ]alimenta[cç][aã]o|aux[ií]lio[- ]refei[cç][aã]o|"
            r"aux[ií]lio[- ]sa[uú]de|cesta b[aá]sica|sacola b[aá]sica|ajuda de custo)[^.;]*",
            "",
            s,
            flags=re.IGNORECASE
        )
        # Se a sentença menciona valor de Médico ou Oficial de Justiça específico quando o cargo não é esse, remover essa cláusula
        if "medico" not in cargos_norm:
            s_sem_beneficios = re.sub(r"Para (?:o cargo de )?M[eé]dicos?[^.;]*", "", s_sem_beneficios, flags=re.IGNORECASE)
        if "oficial de justica" not in cargos_norm:
            s_sem_beneficios = re.sub(r"ressalvada a remunera[cç][aã]o[^.;]*", "", s_sem_beneficios, flags=re.IGNORECASE)

        s_norm = normalize_text(s_sem_beneficios)
        if any(w in s_norm for w in ["varia de", "variam de", "vao de", "vai de", "a r"]):
            eh_faixa = True

        for m in re.findall(padrao_moeda, s_sem_beneficios):
            try:
                val = float(m.replace(".", "").replace(",", "."))
                if 600.0 <= val <= 80000.0:
                    valores_mensais.append(val)
            except ValueError:
                pass

    # 4. Fallback para o resumo do card caso o corpo do artigo não tenha detalhado
    if not valores_mensais and desc_card:
        if "até r$" in desc_card.lower() or "ate r$" in normalize_text(desc_card):
            eh_faixa = True
        for m in re.findall(padrao_moeda, desc_card):
            try:
                val = float(m.replace(".", "").replace(",", "."))
                if 600.0 <= val <= 80000.0:
                    valores_mensais.append(val)
            except ValueError:
                pass

    if valores_mensais:
        maior = round(max(valores_mensais), 2)
        menor = round(min(valores_mensais), 2)
        if eh_faixa and maior != menor:
            return maior, f"Até {formatar_moeda_br(maior)}"
        return maior, formatar_moeda_br(maior)

    return None, "Indisponível"


def classificar_nivel_cargo(header_secao: str, cargo_texto: str, desc_card: str) -> List[str]:
    """
    Determina rigorosamente o nível de escolaridade de um cargo específico de TI
    usando o título do cargo e o cabeçalho da seção onde ele está listado.
    Retorna subconjunto ordenado de ['Médio', 'Técnico', 'Superior'].
    """
    c_norm = normalize_text(cargo_texto)
    h_norm = normalize_text(header_secao)
    d_norm = normalize_text(desc_card)

    # 1. Cargos inequivocamente de Nível Superior pelo próprio título
    if any(k in c_norm for k in [
        "analista", "engenheiro", "engenharia", "professor", "peb ii",
        "cientista", "auditor", "perito", "especialista", "arquiteto"
    ]):
        return ["Superior"]

    # 2. Cargos que trazem 'tecnico' no nome (ex: Técnico de Informática, Técnico em TI, Técnico Judiciário, Agente de Suporte Técnico)
    if "tecnico" in c_norm:
        if "medio" in h_norm and "tecnico" in h_norm:
            return ["Médio", "Técnico"]
        return ["Técnico"]

    # 3. Cargos operacionais / suporte / assistente (ex: Assistente de TI, Auxiliar de Informática, Operador de Computador)
    if any(k in c_norm for k in ["assistente de ti", "auxiliar de ti", "auxiliar de informatica", "operador de", "monitor de informatica", "instrutor de informatica"]):
        if "tecnico" in h_norm and "medio" in h_norm:
            return ["Médio", "Técnico"]
        if "tecnico" in h_norm:
            return ["Técnico"]
        return ["Médio"]

    # 4. Avaliação pelo cabeçalho da seção no <article>
    niveis = []
    if "medio" in h_norm:
        niveis.append("Médio")
    if "tecnico" in h_norm:
        niveis.append("Técnico")
    if any(k in h_norm for k in ["superior", "graduacao", "bacharel", "licenciatura"]):
        niveis.append("Superior")

    if niveis:
        return niveis

    # 5. Avaliação pelo resumo do card quando é cargo único
    if "medio" in d_norm:
        niveis.append("Médio")
    if "tecnico" in d_norm:
        niveis.append("Técnico")
    if "superior" in d_norm:
        niveis.append("Superior")

    return niveis if niveis else ["Superior"]


def classificar_area_atuacao(cargos_list: List[str]) -> List[str]:
    """Classifica em áreas temáticas com base exclusivamente nos cargos de TI do bloco."""
    texto_cargos = normalize_text(" ".join(cargos_list))
    areas = []

    # 1. Dados e IA
    if any(k in texto_cargos for k in [
        "dados", "cientista de dados", "analista de dados", "inteligencia artificial",
        "aprendizado de maquina", "aprendizado profundo", "machine learning", "banco de dados", "dba"
    ]):
        areas.append("Dados e IA")

    # 2. Infraestrutura e Redes
    if any(k in texto_cargos for k in [
        "redes", "suporte", "infraestrutura", "seguranca", "cloud", "nuvem",
        "hardware", "manutencao", "tecnico de informatica", "tecnico em informatica",
        "tecnico em ti", "assistente de ti", "tecnico especializado em informatica"
    ]):
        areas.append("Infraestrutura e Redes")

    # 3. Programação e Sistemas
    if any(k in texto_cargos for k in [
        "programador", "programacao", "desenvolvedor", "desenvolvimento", "sistemas",
        "software", "analista de sistemas", "web", "computacao", "informatica",
        "analista previdenciario ti", "analista tecnico informatica"
    ]):
        areas.append("Programação e Sistemas")

    if not areas:
        areas.append("Programação e Sistemas")

    return sorted(list(set(areas)))


def is_active_deadline(prazo_str: str, referencia_data: Optional[date] = None) -> bool:
    if not prazo_str:
        return False

    if referencia_data is None:
        referencia_data = date.today()

    datas_encontradas = re.findall(r"(\d{2})/(\d{2})/(\d{4})", prazo_str)
    if not datas_encontradas:
        return False

    datas_validas = []
    for d, m, y in datas_encontradas:
        try:
            datas_validas.append(date(int(y), int(m), int(d)))
        except ValueError:
            pass

    if not datas_validas:
        return False

    return max(datas_validas) >= referencia_data


def formatar_tempo_conducao(minutos: int) -> str:
    if minutos <= 0:
        return "0 min"
    if minutos < 60:
        return f"{minutos} min"
    horas = minutos // 60
    resto = minutos % 60
    return f"{horas}h {resto:02d}min" if resto > 0 else f"{horas}h"


class RouteCalculator:
    """
    Calcula distância rodoviária real e tempo de condução a partir de Muzambinho via OpenRouteService.
    Caso a chave da API não esteja configurada, preserva apenas a distância geodésica oficial (IBGE/Haversine)
    e define distância rodoviária/tempo de condução como 'Indisponível' (zero dados inventados).
    """

    def __init__(self, cache_file: Path, api_key: Optional[str] = None):
        self.cache_file = cache_file
        self.api_key = (api_key or os.environ.get("OPENROUTESERVICE_API_KEY", "")).strip()
        self.cache = self._carregar_cache()

    def _carregar_cache(self) -> dict:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                # Filtrar entradas antigas que usavam estimativa sintética 1.25x
                limpo = {
                    k: v for k, v in raw.items()
                    if v.get("fonte_calculo") == "OpenRouteService (driving-car)"
                }
                return limpo
            except Exception:
                return {}
        return {}

    def _salvar_cache(self):
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def calcular_rota(self, cidade: str, uf: str, dest_lat: float, dest_lon: float, linha_reta_km: float) -> dict:
        chave = f"{cidade}-{uf}"

        if linha_reta_km == 0.0:
            return {
                "distancia_carro_km": 0.0,
                "distancia_reta_km": 0.0,
                "tempo_conducao_min": 0,
                "tempo_conducao_formatado": "0 min",
                "fonte_calculo": "Origem (Muzambinho - MG)"
            }

        if chave in self.cache and self.cache[chave].get("fonte_calculo") == "OpenRouteService (driving-car)":
            return self.cache[chave]

        if self.api_key:
            try:
                url = "https://api.openrouteservice.org/v2/directions/driving-car"
                body = json.dumps({
                    "coordinates": [[MUZAMBINHO_LON, MUZAMBINHO_LAT], [dest_lon, dest_lat]]
                }).encode("utf-8")
                headers = {
                    "Authorization": self.api_key,
                    "Content-Type": "application/json"
                }
                req = urllib.request.Request(url, data=body, headers=headers)
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    summary = data["routes"][0]["summary"]
                    dist_km = round(summary["distance"] / 1000.0, 1)
                    dur_min = int(round(summary["duration"] / 60.0))

                    resultado = {
                        "distancia_carro_km": dist_km,
                        "distancia_reta_km": linha_reta_km,
                        "tempo_conducao_min": dur_min,
                        "tempo_conducao_formatado": formatar_tempo_conducao(dur_min),
                        "fonte_calculo": "OpenRouteService (driving-car)"
                    }
                    self.cache[chave] = resultado
                    self._salvar_cache()
                    return resultado
            except Exception as e:
                logger.warning(f"Falha ao consultar OpenRouteService para {chave}: {e}")

        # Sem chave da API ou falha de rede: não inventar distância rodoviária nem tempo de condução
        return {
            "distancia_carro_km": None,
            "distancia_reta_km": linha_reta_km,
            "tempo_conducao_min": None,
            "tempo_conducao_formatado": "Indisponível",
            "fonte_calculo": "Geodésico Oficial IBGE (Linha Reta)"
        }


@dataclass
class Municipio:
    nome: str
    nome_norm: str
    uf: str
    lat: float
    lon: float
    distancia_muzambinho_km: float = 0.0


@dataclass
class Concurso:
    id: str
    orgao: str
    cidade: str
    uf: str
    distancia_km: float  # Distância de referência para ordenação (carro quando ORS ativo, senão linha reta)
    distancia_carro_km: Optional[float]
    distancia_reta_km: float
    tempo_conducao_min: Optional[int]
    tempo_conducao_formatado: str
    fonte_calculo_distancia: str
    titulo: str
    link_pci: str
    link_edital_oficial: str
    banca_organizadora: str
    vagas_salario: str
    salario_num: Optional[float]
    salario_formatado: str
    escolaridade_niveis: List[str]
    areas_atuacao: List[str]
    data_limite_inscricao: str
    cargos_ti_identificados: List[str] = field(default_factory=list)
    data_extracao: str = field(default_factory=lambda: datetime.now().isoformat())


class BaseMunicipios:
    """Gerencia base oficial IBGE de coordenadas de MG, SP e RJ."""

    def __init__(self, data_file: Path):
        self.data_file = data_file
        self.municipios: Dict[Tuple[str, str], Municipio] = {}
        self.sorted_mg: List[Tuple[str, Municipio]] = []
        self.sorted_sp: List[Tuple[str, Municipio]] = []
        self.sorted_rj: List[Tuple[str, Municipio]] = []
        self._carregar_ou_baixar()

    def _carregar_ou_baixar(self):
        if self.data_file.exists():
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    dados = json.load(f)
                self._popular_dados(dados)
                logger.info(f"Carregados {len(self.municipios)} municípios oficiais IBGE de {self.data_file}")
                return
            except Exception as e:
                logger.warning(f"Erro ao ler cache de municípios ({e}). Baixando dados...")

        self._baixar_e_processar()

    def _baixar_e_processar(self):
        url = "https://raw.githubusercontent.com/kelvins/Municipios-Brasileiros/main/csv/municipios.csv"
        logger.info(f"Baixando base oficial de municípios de {url}...")
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as resp:
            conteudo = resp.read().decode("utf-8")

        reader = csv.DictReader(io.StringIO(conteudo))
        dados = []
        for row in reader:
            codigo_uf = row.get("codigo_uf")
            uf = "MG" if codigo_uf == "31" else ("SP" if codigo_uf == "35" else ("RJ" if codigo_uf == "33" else None))
            if uf:
                nome = row["nome"]
                dados.append({
                    "nome": nome,
                    "nome_norm": normalize_text(nome),
                    "uf": uf,
                    "lat": float(row["latitude"]),
                    "lon": float(row["longitude"])
                })

        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)

        self._popular_dados(dados)

    def _popular_dados(self, dados: List[dict]):
        self.municipios.clear()
        for item in dados:
            m = Municipio(
                nome=item["nome"],
                nome_norm=item["nome_norm"],
                uf=item["uf"],
                lat=item["lat"],
                lon=item["lon"],
                distancia_muzambinho_km=round(
                    haversine_distance(MUZAMBINHO_LAT, MUZAMBINHO_LON, item["lat"], item["lon"]), 1
                )
            )
            self.municipios[(m.nome_norm, m.uf)] = m

        mg_list = [(k[0], v) for k, v in self.municipios.items() if k[1] == "MG"]
        sp_list = [(k[0], v) for k, v in self.municipios.items() if k[1] == "SP"]
        rj_list = [(k[0], v) for k, v in self.municipios.items() if k[1] == "RJ"]
        self.sorted_mg = sorted(mg_list, key=lambda x: len(x[0]), reverse=True)
        self.sorted_sp = sorted(sp_list, key=lambda x: len(x[0]), reverse=True)
        self.sorted_rj = sorted(rj_list, key=lambda x: len(x[0]), reverse=True)

    def identificar_municipios_no_texto(self, texto: str, uf: str) -> List[Municipio]:
        """
        Retorna todos os municípios não-sobrepostos encontrados no texto,
        ordenados pela menor distância até Muzambinho.
        """
        norm_texto = normalize_text(texto)
        if not norm_texto:
            return []

        if uf == "MG":
            candidatos = self.sorted_mg
        elif uf == "SP":
            candidatos = self.sorted_sp
        elif uf == "RJ":
            candidatos = self.sorted_rj
        else:
            candidatos = self.sorted_mg + self.sorted_sp + self.sorted_rj

        intervalos_ocupados: List[Tuple[int, int]] = []
        encontrados: Dict[Tuple[str, str], Municipio] = {}

        for nome_norm, municipio in candidatos:
            if len(nome_norm) < 3:
                continue
            padrao = r"\b" + re.escape(nome_norm) + r"\b"
            for m in re.finditer(padrao, norm_texto):
                ini, fim = m.span()
                if not any(not (fim <= o_ini or ini >= o_fim) for o_ini, o_fim in intervalos_ocupados):
                    intervalos_ocupados.append((ini, fim))
                    encontrados[(municipio.nome_norm, municipio.uf)] = municipio

        return sorted(encontrados.values(), key=lambda x: x.distancia_muzambinho_km)

    def identificar_municipio(self, texto: str, uf: str) -> Optional[Municipio]:
        achados = self.identificar_municipios_no_texto(texto, uf)
        return achados[0] if achados else None


class ConcursosSudesteScraper:
    """Extrai editais de TI no raio configurado, separa blocos por escolaridade e resolve links diretos."""

    def __init__(self, base_municipios: BaseMunicipios, route_calc: RouteCalculator, raio_max_km: float = 250.0):
        self.base_municipios = base_municipios
        self.route_calc = route_calc
        self.raio_max_km = raio_max_km
        self._banca_html_cache: Dict[str, str] = {}

    def _fazer_requisicao(self, url: str, timeout: int = 15) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")

    def _resolver_link_direto_banca(self, banca_url: str, orgao: str, cidade: str) -> str:
        """
        Quando o link do artigo aponta para a home de uma banca organizadora,
        inspeciona a página da banca para encontrar o link direto do concurso específico.
        Se não houver link profundo estático, mantém o link oficial da banca.
        """
        if not banca_url or not banca_url.startswith("http"):
            return "Indisponível"

        parsed = urllib.parse.urlparse(banca_url)
        # Se a URL já possui caminho profundo específico (ex: /informacoes/109/, /node/100, forms.gle/...), manter
        if parsed.path and parsed.path.strip("/") and not parsed.path.strip("/").startswith("v2"):
            return banca_url

        try:
            if banca_url not in self._banca_html_cache:
                self._banca_html_cache[banca_url] = self._fazer_requisicao(banca_url, timeout=7)
            html = self._banca_html_cache[banca_url]

            norm_cid = normalize_text(cidade)
            sigla_org = normalize_text(orgao.split("-")[0])
            # Se a própria URL da banca já contém a sigla do órgão (ex: concursopublico.ifsp.edu.br),
            # não usar a sigla sozinha como critério de link profundo para evitar links institucionais (acessibilidade, etc.)
            usar_sigla = bool(sigla_org and len(sigla_org) > 2 and sigla_org not in normalize_text(banca_url))

            links_utilitarios = (
                "acessibilidade", "ouvidoria", "fale-conosco", "contato", "quem-somos",
                "institucional", "privacidade", "lgpd", "login", " AreaRestrita", "faq", "ajuda", "libras"
            )

            # Passagem 1: Texto ou href da âncora contém o nome da cidade ou sigla do órgão
            for m in re.finditer(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.DOTALL | re.IGNORECASE):
                href = m.group(1).strip()
                if href.startswith(("#", "javascript", "mailto", "tel")):
                    continue
                if any(u.lower() in href.lower() for u in links_utilitarios):
                    continue
                full_url = urllib.parse.urljoin(banca_url, href)
                if full_url.rstrip("/") == banca_url.rstrip("/"):
                    continue
                text_norm = normalize_text(re.sub(r"<[^>]+>", " ", m.group(2)))
                href_norm = normalize_text(href)
                if any(u.lower() in text_norm for u in links_utilitarios):
                    continue
                if (norm_cid and len(norm_cid) > 3 and (norm_cid in text_norm or norm_cid in href_norm)) or (
                    usar_sigla and (sigla_org in text_norm or sigla_org in href_norm)
                ):
                    return full_url

            # Passagem 2: Contexto imediatamente anterior ao link menciona a cidade ou órgão
            for m in re.finditer(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.DOTALL | re.IGNORECASE):
                href = m.group(1).strip()
                if href.startswith(("#", "javascript", "mailto", "tel")):
                    continue
                if any(u.lower() in href.lower() for u in links_utilitarios):
                    continue
                full_url = urllib.parse.urljoin(banca_url, href)
                if full_url.rstrip("/") == banca_url.rstrip("/"):
                    continue
                ctx_before = normalize_text(re.sub(r"<[^>]+>", " ", html[max(0, m.start() - 300):m.start()]))
                if (norm_cid and len(norm_cid) > 3 and norm_cid in ctx_before) or (
                    usar_sigla and sigla_org in ctx_before
                ):
                    return full_url
        except Exception:
            pass

        return banca_url

    def _extrair_link_edital_e_banca(self, art_html: str, orgao: str, cidade: str) -> Tuple[str, str]:
        """
        Extrai o link externo mais direto para inscrição/edital dentro do <article>
        e identifica o nome/domínio da banca organizadora.
        """
        links_externos: List[Tuple[str, str]] = []
        for m in re.finditer(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', art_html, re.DOTALL | re.IGNORECASE):
            href = m.group(1).strip()
            texto = " ".join(re.sub(r"<[^>]+>", " ", m.group(2)).split())
            if not href.startswith("http"):
                continue
            if any(ign in href.lower() for ign in ["pciconcursos.com.br", "t.me/", "linkedin.com", "x.com/", "twitter.com", "facebook.com", "instagram.com", "unpkg.com", "openstreetmap.org"]):
                continue
            # Corrigir URLs duplicadas acidentais no HTML da fonte (ex: https://setec.sp.gov.br/https:/setec.sp.gov.br/)
            if href.count("http") > 1:
                partes = [p for p in re.split(r"(?=https?:/+)", href) if p.startswith("http")]
                if partes:
                    href = partes[0]
            links_externos.append((href, texto))

        if not links_externos:
            return "Indisponível", "Indisponível"

        # Preferir o link que aparece no parágrafo de inscrições (geralmente o 2º link externo, que é a banca/sistema de inscrição)
        link_escolhido, texto_escolhido = links_externos[-1]
        for href, texto in links_externos:
            # Se é um formulário ou portal de seleção específico, priorizar
            if any(k in href.lower() for k in ["selecao", "concurso", "inscric", "sigrh", "uspdigital", "forms.gle", "vunesp", "ibfc", "ibgp", "fcc", "aocp", "glconsultoria", "idepi", "cmmconcursos", "abconcursos"]):
                link_escolhido, texto_escolhido = href, texto
                break

        link_direto = self._resolver_link_direto_banca(link_escolhido, orgao, cidade)
        dominio = urllib.parse.urlparse(link_direto).netloc.replace("www.", "")
        banca_nome = texto_escolhido if (texto_escolhido and len(texto_escolhido) <= 45 and not texto_escolhido.startswith("http")) else dominio
        return link_direto, (banca_nome or "Indisponível")

    def buscar_concursos(self) -> List[Concurso]:
        todos_cards_brutos = {}
        padrao_card = re.compile(
            r'<div class="ca">\s*<a href="(?P<link>[^"]+)"\s+title="(?P<titulo>[^"]+)"[^>]*>(?P<orgao>[^<]+)</a>'
            r'.*?<div class="cc">(?P<uf>[^<]+)</div>'
            r'.*?<div class="cd">(?P<desc>.*?)</div>\s*<div class="ce"><span>(?P<prazo>.*?)</span></div>',
            re.DOTALL
        )

        logger.info(f"Varrendo {len(FONTES_CONCURSOS)} canais oficiais no PCI Concursos...")
        for url_fonte, nome_fonte in FONTES_CONCURSOS:
            try:
                html = self._fazer_requisicao(url_fonte)
                matches = list(padrao_card.finditer(html))
                novos = 0
                for m in matches:
                    link = m.group("link").strip()
                    if link not in todos_cards_brutos:
                        todos_cards_brutos[link] = {
                            "link": link,
                            "titulo": m.group("titulo").strip(),
                            "orgao": m.group("orgao").strip(),
                            "uf": m.group("uf").strip(),
                            "desc": " ".join(re.sub(r"<[^>]+>", " ", m.group("desc")).split()),
                            "prazo": " ".join(re.sub(r"<[^>]+>", " ", m.group("prazo")).split()),
                            "origens": [nome_fonte]
                        }
                        novos += 1
                    else:
                        if nome_fonte not in todos_cards_brutos[link]["origens"]:
                            todos_cards_brutos[link]["origens"].append(nome_fonte)
                logger.info(f"  -> [{nome_fonte}] {len(matches)} editais ({novos} inéditos).")
            except Exception as e:
                logger.warning(f"Erro na fonte {url_fonte}: {e}")

        logger.info(f"Total consolidado de editais únicos coletados: {len(todos_cards_brutos)}")

        # Pré-filtragem por Prazo Ativo, Escolaridade (Médio/Técnico/Superior) e UF (MG, SP, RJ)
        candidatos_para_inspecao = []
        for link, c in todos_cards_brutos.items():
            if not is_active_deadline(c["prazo"]):
                continue

            desc_norm = normalize_text(c["desc"])
            if not any(k in desc_norm for k in ["medio", "tecnico", "superior"]):
                continue

            uf = c["uf"]
            norm_tit_org = normalize_text(f"{c['titulo']} {c['orgao']}")
            if uf not in ("MG", "SP", "RJ"):
                if " mg " in f" {norm_tit_org} " or " minas gerais " in f" {norm_tit_org} ":
                    uf = "MG"
                elif " sp " in f" {norm_tit_org} " or " sao paulo " in f" {norm_tit_org} ":
                    uf = "SP"
                elif " rj " in f" {norm_tit_org} " or " rio de janeiro " in f" {norm_tit_org} ":
                    uf = "RJ"
                else:
                    continue

            c["uf_resolved"] = uf
            slug_url = link.split("/")[-1]
            texto_busca = f"{c['orgao']} {c['titulo']} {slug_url}"
            mun_titulo = self.base_municipios.identificar_municipio(texto_busca, uf)

            # Se o título já crava uma única cidade fora do raio de 250km (e não é órgão estadual/federal multicampi), pular
            eh_multicampi = any(
                sigla in normalize_text(c["orgao"])
                for sigla in ["ifsp", "ifmg", "ifsuldeminas", "unesp", "usp", "unifei", "cefet", "trf", "sefaz", "marinha", "mgs", "emater"]
            )
            if mun_titulo and mun_titulo.distancia_muzambinho_km > self.raio_max_km and not eh_multicampi:
                continue

            # Otimização: só inspecionar a página interna se o card veio de um canal de TI,
            # ou menciona termo de TI no card, ou é "Vários Cargos" / multicampi
            veio_canal_ti = any(o not in ("Sudeste", "Nacional") for o in c["origens"])
            tem_termo_card = bool(IT_CARGO_REGEX.search(normalize_text(f"{c['desc']} {c['titulo']}")))
            eh_varios_cargos = "varios cargos" in desc_norm

            if veio_canal_ti or tem_termo_card or eh_varios_cargos:
                c["mun_titulo"] = mun_titulo
                c["eh_multicampi"] = eh_multicampi
                candidatos_para_inspecao.append(c)

        logger.info(f"Candidatos ativos pré-selecionados para inspeção estrutural de cargos: {len(candidatos_para_inspecao)}")

        concursos_extraidos: List[Concurso] = []
        chaves_dedup = set()

        for idx, item in enumerate(candidatos_para_inspecao, 1):
            blocos = self._inspecionar_e_separar_blocos(item)
            for conc in blocos:
                # Chave rigorosa de desduplicação: (órgão normalizado, cidade, uf, níveis, cargos normalizados)
                org_key = normalize_text(conc.orgao.split("-")[0])
                niv_key = ",".join(conc.escolaridade_niveis)
                cargos_key = "|".join(sorted(normalize_text(cg) for cg in conc.cargos_ti_identificados))
                dedup_id = (org_key, conc.cidade, conc.uf, niv_key, cargos_key)

                if dedup_id in chaves_dedup:
                    continue
                chaves_dedup.add(dedup_id)

                logger.info(
                    f"[{idx}/{len(candidatos_para_inspecao)}] [TI CONFIRMADO] "
                    f"{conc.cidade}-{conc.uf} ({conc.distancia_reta_km}km reta) | "
                    f"Nível: {'/'.join(conc.escolaridade_niveis)} | "
                    f"Salário: {conc.salario_formatado} | {conc.orgao} -> {conc.cargos_ti_identificados}"
                )
                concursos_extraidos.append(conc)
            time.sleep(0.08)

        concursos_extraidos.sort(key=lambda x: (x.distancia_km, -(x.salario_num or 0)))
        return concursos_extraidos

    def _inspecionar_e_separar_blocos(self, item: dict) -> List[Concurso]:
        """
        Acessa a página do concurso, extrai os cargos reais de TI em <li>,
        filtra cargos lotados em cidades dentro do raio de 250km e divide em blocos
        distintos caso o edital possua vagas de nível Médio/Técnico e Superior juntas.
        """
        try:
            page_html = self._fazer_requisicao(item["link"])
        except Exception as e:
            logger.warning(f"Erro ao acessar {item['link']}: {e}")
            return []

        art_m = re.search(r"<article[^>]*>(.*?)</article>", page_html, re.DOTALL)
        if not art_m:
            return []
        art_html = art_m.group(1)

        uf = item["uf_resolved"]
        mun_base = item.get("mun_titulo")

        # Se o município não estava no título do card, tentar extrair do objeto IBGE embutido na página (var cidade = {...})
        if not mun_base:
            m_cid = re.search(r'var\s+cidade\s*=\s*\{[^}]*"nome"\s*:\s*"([^"]+)"', page_html)
            if m_cid:
                mun_base = self.base_municipios.identificar_municipio(m_cid.group(1), uf)

        # Extrair sequência de parágrafos/cabeçalhos e itens de lista (cargos)
        tokens = re.findall(r"<(p|li|h2|h3|h4)[^>]*>(.*?)</\1>", art_html, re.DOTALL)
        paragrafos_artigo: List[str] = []
        header_atual = ""
        cargos_ti_validos: List[Tuple[str, str, Optional[Municipio]]] = []

        for tag, raw_txt in tokens:
            clean = " ".join(re.sub(r"<[^>]+>", " ", raw_txt).split())
            if not clean:
                continue
            norm = normalize_text(clean)
            if tag in ("p", "h2", "h3", "h4"):
                paragrafos_artigo.append(clean)
                if len(clean) < 110 and not any(k in norm for k in ["jornada", "remuneracao", "inscricoes", "validade", "selecao"]):
                    header_atual = clean
            elif tag == "li":
                # Ignorar links de formulário que repetem o cargo
                if "http://" in clean.lower() or "https://" in clean.lower():
                    clean = re.sub(r":?\s*https?://\S+", "", clean).strip()
                    norm = normalize_text(clean)

                if IT_CARGO_REGEX.search(norm) and not EXCLUDE_CARGO_REGEX.search(norm):
                    # Verificar se o próprio item <li> ou o cabeçalho especifica uma cidade/campus
                    mun_cargo = None
                    if "mato grosso do sul" in normalize_text(header_atual) or "/rj" in clean.lower():
                        # Cargo lotado em outro estado fora da região de alcance
                        continue

                    muns_li = self.base_municipios.identificar_municipios_no_texto(clean, uf)
                    if muns_li:
                        mun_cargo = muns_li[0]
                    else:
                        muns_hdr = self.base_municipios.identificar_municipios_no_texto(header_atual, uf)
                        if muns_hdr:
                            mun_cargo = muns_hdr[0]

                    # Se o cargo tem lotação explícita fora do raio de 250km, descartar este cargo
                    if mun_cargo and mun_cargo.distancia_muzambinho_km > self.raio_max_km:
                        continue

                    cargos_ti_validos.append((header_atual, clean, mun_cargo))

        if not cargos_ti_validos:
            return []

        # Determinar o município final do edital (dentro do raio de 250km)
        muns_dos_cargos = [mc for _, _, mc in cargos_ti_validos if mc is not None and mc.distancia_muzambinho_km <= self.raio_max_km]
        if muns_dos_cargos:
            muns_dos_cargos.sort(key=lambda x: x.distancia_muzambinho_km)
            municipio_final = muns_dos_cargos[0]
        elif mun_base and mun_base.distancia_muzambinho_km <= self.raio_max_km:
            municipio_final = mun_base
        else:
            # Procurar municípios mencionados no texto do artigo (ex: MGS mencionando Guaxupé, ou SEFAZ/TRF3 em São Paulo)
            texto_artigo_completo = " ".join(paragrafos_artigo)
            muns_artigo = [
                m for m in self.base_municipios.identificar_municipios_no_texto(texto_artigo_completo, uf)
                if m.distancia_muzambinho_km <= self.raio_max_km
            ]
            if muns_artigo:
                municipio_final = muns_artigo[0]
            elif uf == "SP" and any(s in normalize_text(item["orgao"]) for s in ["trf3", "sefaz", "marinha"]):
                municipio_final = self.base_municipios.municipios.get(("sao paulo", "SP"))
            else:
                return []

        if not municipio_final or municipio_final.distancia_muzambinho_km > self.raio_max_km:
            return []

        # Separar os cargos de TI encontrados em Bloco Médio/Técnico vs Bloco Superior
        bloco_mt_cargos: List[str] = []
        bloco_mt_niveis = set()
        bloco_sup_cargos: List[str] = []

        for hdr, cargo_str, mc in cargos_ti_validos:
            # Se o cabeçalho era o nome do campus (ex: IFSP Substituto) e não está no texto do cargo, anexar o campus
            if mc and normalize_text(mc.nome) not in normalize_text(cargo_str):
                cargo_exibicao = f"{cargo_str} - {mc.nome}"
            elif (
                hdr
                and len(hdr) <= 30
                and not any(w in normalize_text(hdr) for w in ["ensino", "nivel", "edital", "segundo", "concurso", "processo", "area", "tribunal", "secao"])
                and normalize_text(hdr) not in normalize_text(cargo_str)
            ):
                cargo_exibicao = f"{cargo_str} - {hdr}"
            else:
                cargo_exibicao = cargo_str

            niveis_cargo = classificar_nivel_cargo(hdr, cargo_str, item["desc"])
            if "Superior" in niveis_cargo and len(niveis_cargo) == 1:
                if cargo_exibicao not in bloco_sup_cargos:
                    bloco_sup_cargos.append(cargo_exibicao)
            else:
                for nv in niveis_cargo:
                    if nv in ("Médio", "Técnico"):
                        bloco_mt_niveis.add(nv)
                if not bloco_mt_niveis:
                    bloco_mt_niveis.add("Técnico")
                if cargo_exibicao not in bloco_mt_cargos:
                    bloco_mt_cargos.append(cargo_exibicao)

        # Calcular rota real (ou linha reta IBGE se sem chave ORS)
        rota = self.route_calc.calcular_rota(
            cidade=municipio_final.nome,
            uf=municipio_final.uf,
            dest_lat=municipio_final.lat,
            dest_lon=municipio_final.lon,
            linha_reta_km=municipio_final.distancia_muzambinho_km
        )
        dist_referencia = rota["distancia_carro_km"] if rota["distancia_carro_km"] is not None else rota["distancia_reta_km"]

        # Extrair link oficial direto e banca organizadora
        link_direto, banca_nome = self._extrair_link_edital_e_banca(art_html, item["orgao"], municipio_final.nome)

        id_base = re.sub(r"[^a-zA-Z0-9]", "", item["link"].split("/")[-1])
        tem_ambos_blocos = bool(bloco_mt_cargos and bloco_sup_cargos)
        registros_finais: List[Concurso] = []

        # Emitir Bloco 1: Médio / Técnico (se houver cargos de nível médio/técnico)
        if bloco_mt_cargos:
            niveis_ordenados_mt = [nv for nv in ["Médio", "Técnico"] if nv in bloco_mt_niveis]
            sal_num_mt, sal_fmt_mt = extrair_salario_bloco(paragrafos_artigo, item["desc"], "MEDIO_TECNICO", bloco_mt_cargos)
            areas_mt = classificar_area_atuacao(bloco_mt_cargos)
            orgao_mt = f"{item['orgao']} (Nível {' / '.join(niveis_ordenados_mt)})" if tem_ambos_blocos else item["orgao"]

            registros_finais.append(
                Concurso(
                    id=f"{id_base}-mt",
                    orgao=orgao_mt,
                    cidade=municipio_final.nome,
                    uf=municipio_final.uf,
                    distancia_km=dist_referencia,
                    distancia_carro_km=rota["distancia_carro_km"],
                    distancia_reta_km=rota["distancia_reta_km"],
                    tempo_conducao_min=rota["tempo_conducao_min"],
                    tempo_conducao_formatado=rota["tempo_conducao_formatado"],
                    fonte_calculo_distancia=rota["fonte_calculo"],
                    titulo=item["titulo"],
                    link_pci=item["link"],
                    link_edital_oficial=link_direto,
                    banca_organizadora=banca_nome,
                    vagas_salario=item["desc"],
                    salario_num=sal_num_mt,
                    salario_formatado=sal_fmt_mt,
                    escolaridade_niveis=niveis_ordenados_mt,
                    areas_atuacao=areas_mt,
                    data_limite_inscricao=item["prazo"] or "Indisponível",
                    cargos_ti_identificados=bloco_mt_cargos
                )
            )

        # Emitir Bloco 2: Superior (se houver cargos de nível superior)
        if bloco_sup_cargos:
            sal_num_sup, sal_fmt_sup = extrair_salario_bloco(paragrafos_artigo, item["desc"], "SUPERIOR", bloco_sup_cargos)
            areas_sup = classificar_area_atuacao(bloco_sup_cargos)
            orgao_sup = f"{item['orgao']} (Nível Superior)" if tem_ambos_blocos else item["orgao"]

            registros_finais.append(
                Concurso(
                    id=f"{id_base}-sup",
                    orgao=orgao_sup,
                    cidade=municipio_final.nome,
                    uf=municipio_final.uf,
                    distancia_km=dist_referencia,
                    distancia_carro_km=rota["distancia_carro_km"],
                    distancia_reta_km=rota["distancia_reta_km"],
                    tempo_conducao_min=rota["tempo_conducao_min"],
                    tempo_conducao_formatado=rota["tempo_conducao_formatado"],
                    fonte_calculo_distancia=rota["fonte_calculo"],
                    titulo=item["titulo"],
                    link_pci=item["link"],
                    link_edital_oficial=link_direto,
                    banca_organizadora=banca_nome,
                    vagas_salario=item["desc"],
                    salario_num=sal_num_sup,
                    salario_formatado=sal_fmt_sup,
                    escolaridade_niveis=["Superior"],
                    areas_atuacao=areas_sup,
                    data_limite_inscricao=item["prazo"] or "Indisponível",
                    cargos_ti_identificados=bloco_sup_cargos
                )
            )

        return registros_finais


class ConcursosExporter:
    @staticmethod
    def exportar_json(concursos: List[Concurso], arquivo_saida: Path, parametros: dict, ors_ativo: bool):
        arquivo_saida.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "metadados": {
                "gerado_em": datetime.now().isoformat(),
                "cidade_origem": parametros.get("origem", "Muzambinho - MG"),
                "coordenadas_origem": [MUZAMBINHO_LAT, MUZAMBINHO_LON],
                "raio_max_km": parametros.get("raio", 250.0),
                "openrouteservice_ativo": ors_ativo,
                "metodo_distancia_ativo": "OpenRouteService (driving-car)" if ors_ativo else "Geodésico Oficial IBGE (Linha Reta)",
                "escopo_escolaridade": ["Médio", "Técnico", "Superior"],
                "area_atuacao": "Tecnologia da Informação / Computação",
                "total_editais_encontrados": len(concursos),
                "total_canais_monitorados": len(FONTES_CONCURSOS),
                "fontes_consultadas": [nome for _, nome in FONTES_CONCURSOS]
            },
            "editais": [asdict(c) for c in concursos]
        }

        with open(arquivo_saida, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        logger.info(f"Arquivo exportado com sucesso: {arquivo_saida}")


def executar_varredura(raio: float, arquivo_saida: Path, base_data_dir: Path, ors_key: Optional[str] = None, force: bool = False) -> bool:
    INTERVALO_BLOQUEIO_SEGUNDOS = 3 * 3600  # Bloqueio geral de 3 horas (10.800 segundos)

    # Verificação de Bloqueio Geral Independente de Sessão
    if not force and arquivo_saida.exists():
        try:
            with open(arquivo_saida, "r", encoding="utf-8") as f:
                dados_existentes = json.load(f)
                gerado_em_str = dados_existentes.get("metadados", {}).get("gerado_em")
                if gerado_em_str:
                    clean_str = gerado_em_str.replace("Z", "+00:00")
                    dt_gerado = datetime.fromisoformat(clean_str)
                    if dt_gerado.tzinfo is not None:
                        dt_gerado = dt_gerado.astimezone().replace(tzinfo=None)
                    tempo_decorrido = (datetime.now() - dt_gerado).total_seconds()
                    if tempo_decorrido < INTERVALO_BLOQUEIO_SEGUNDOS:
                        segundos_restantes = int(INTERVALO_BLOQUEIO_SEGUNDOS - tempo_decorrido)
                        horas = segundos_restantes // 3600
                        minutos = (segundos_restantes % 3600) // 60
                        logger.warning("=" * 72)
                        logger.warning(f"[BLOQUEIO GERAL ATIVO] A última varredura foi gerada há {int(tempo_decorrido // 60)} min.")
                        logger.warning("O sistema possui um bloqueio geral de 3 horas entre varreduras para proteger os servidores de origem.")
                        logger.warning(f"Tempo restante de bloqueio: {horas}h {minutos}m. Execução cancelada.")
                        logger.warning("Para ignorar esta trava e executar mesmo assim, utilize o parâmetro --force.")
                        logger.warning("=" * 72)
                        return False
        except Exception as e:
            logger.warning(f"Não foi possível verificar timestamp da última varredura ({e}). Prosseguindo...")

    logger.info("=" * 72)
    logger.info(f"INICIANDO RADAR DE CONCURSOS TI - MUZAMBINHO & RAIO DE ATÉ {raio}KM")
    logger.info("=" * 72)

    caminho_base = base_data_dir / "municipios_mg_sp.json"
    cache_rotas = base_data_dir / "distancias_cache.json"

    base_municipios = BaseMunicipios(caminho_base)
    route_calc = RouteCalculator(cache_rotas, api_key=ors_key)

    scraper = ConcursosSudesteScraper(base_municipios, route_calc, raio_max_km=raio)
    concursos = scraper.buscar_concursos()

    parametros = {
        "origem": "Muzambinho - MG",
        "raio": raio
    }
    ConcursosExporter.exportar_json(
        concursos,
        arquivo_saida,
        parametros,
        ors_ativo=bool(route_calc.api_key)
    )

    logger.info("=" * 72)
    logger.info(f"VARREDURA FINALIZADA! {len(concursos)} bloco(s) de editais de TI localizado(s).")
    logger.info(f"Arquivo gerado: {arquivo_saida.resolve()}")
    logger.info("=" * 72)
    return True


def iniciar_agendador(raio: float, arquivo_saida: Path, base_data_dir: Path, hora_execucao: str = "08:00", ors_key: Optional[str] = None):
    logger.info(f"Modo Agendador ativado: Segundas, Quartas e Sextas às {hora_execucao}.")
    logger.info("Pressione Ctrl+C para encerrar o serviço.")

    dias_alvo = {0: "Segunda-feira", 2: "Quarta-feira", 4: "Sexta-feira"}
    hora_alvo, minuto_alvo = map(int, hora_execucao.split(":"))
    ultimo_dia_executado = -1

    while True:
        agora = datetime.now()
        dia_da_semana = agora.weekday()

        if dia_da_semana in dias_alvo:
            if agora.hour == hora_alvo and agora.minute == minuto_alvo and ultimo_dia_executado != agora.day:
                logger.info(f"Disparo programado ({dias_alvo[dia_da_semana]}) iniciado.")
                try:
                    executar_varredura(raio, arquivo_saida, base_data_dir, ors_key, force=True)
                    ultimo_dia_executado = agora.day
                except Exception as e:
                    logger.error(f"Erro na execução programada: {e}", exc_info=True)

        time.sleep(30)


def main():
    parser = argparse.ArgumentParser(
        description="Radar de Concursos TI com separação por nível (Médio/Técnico > Superior) e integração OpenRouteService."
    )
    parser.add_argument(
        "--raio",
        type=float,
        default=250.0,
        help="Raio máximo em quilômetros a partir de Muzambinho (padrão: 250.0)"
    )
    parser.add_argument(
        "--saida",
        type=str,
        default="concursos_muzambinho_ti.json",
        help="Caminho do arquivo JSON de saída (padrão: concursos_muzambinho_ti.json)"
    )
    parser.add_argument(
        "--agendar",
        action="store_true",
        help="Mantém o script em execução contínua para rodar toda Seg, Qua e Sex"
    )
    parser.add_argument(
        "--hora",
        type=str,
        default="08:00",
        help="Horário de execução nos dias agendados no formato HH:MM (padrão: 08:00)"
    )
    parser.add_argument(
        "--ors-key",
        type=str,
        default=None,
        help="Chave da API OpenRouteService (ou defina a variável de ambiente OPENROUTESERVICE_API_KEY)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignora o bloqueio geral de 3 horas e força uma nova varredura imediatamente"
    )

    args = parser.parse_args()
    diretorio_script = Path(__file__).resolve().parent
    arquivo_saida = Path(args.saida)
    if not arquivo_saida.is_absolute():
        arquivo_saida = diretorio_script / arquivo_saida

    base_data_dir = diretorio_script / "data"

    executar_varredura(
        raio=args.raio,
        arquivo_saida=arquivo_saida,
        base_data_dir=base_data_dir,
        ors_key=args.ors_key,
        force=args.force
    )

    if args.agendar:
        iniciar_agendador(
            raio=args.raio,
            arquivo_saida=arquivo_saida,
            base_data_dir=base_data_dir,
            hora_execucao=args.hora,
            ors_key=args.ors_key
        )


if __name__ == "__main__":
    main()
