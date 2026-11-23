"""Página web estática da tipologia para o coordenador: python src/pagina.py <cenário> <algoritmo> <k>."""
import base64
import sys
import unicodedata
from html import escape
from pathlib import Path
import pandas as pd
from modelo import CENARIOS
RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "data" / "output"
WEB = RAIZ / "data" / "web"
if len(sys.argv) != 4 or sys.argv[1] not in CENARIOS or sys.argv[2] not in ["kmeans", "ward", "kmedoids"] or not sys.argv[3].isdigit():
    sys.exit("Uso: python src/pagina.py <C1|C2> <kmeans|ward|kmedoids> <k>   por exemplo: python src/pagina.py C1 kmeans 4")
CENARIO = sys.argv[1]
ALGORITMO = sys.argv[2]
K = int(sys.argv[3])
nome = f"{CENARIO}_{ALGORITMO}_k{K}"
if not (SAIDA / f"perfis_grupos_{nome}.csv").exists():
    sys.exit(f"Faltam os perfis desta combinação. Execute antes: python src/perfis.py {CENARIO} {ALGORITMO} {K}")
if not (WEB / "bootstrap.min.css").exists() or not (WEB / "brasao_preto_vertical.svg").exists():
    sys.exit("Faltam data/web/bootstrap.min.css ou data/web/brasao_preto_vertical.svg")
NOMES = {"pop_0a4_pct": "Crianças 0-4 anos (%)", "pop_60m_pct": "Idosos 60+ (%)",
         "agua_adeq_pct": "Água adequada (%)", "agua_prec_pct": "Água precária (%)",
         "agua_sem_pct": "Água sem atendimento (%)", "esg_adeq_pct": "Esgoto adequado (%)",
         "esg_prec_pct": "Esgoto precário (%)", "esg_sem_pct": "Esgoto sem atendimento (%)",
         "rural_pct": "População rural (%)", "idade_pres_pct": "Idade presumida (%)"}
CORES = ["#1d4e89", "#c8641a", "#2a9d8f", "#c1121f", "#6a4c93", "#b5179e", "#588157", "#5c677d"]

perfis_grupos = pd.read_csv(SAIDA / f"perfis_grupos_{nome}.csv", index_col=0)
atribuicao = pd.read_csv(SAIDA / f"atribuicao_municipios_{nome}.csv", index_col="cod_mun")
indicadores = pd.read_csv(SAIDA / "indicadores_municipio.csv", index_col="cod_mun")
variaveis_modelo = pd.read_csv(SAIDA / "matriz_modelo.csv", index_col="cod_mun").columns
bootstrap = (WEB / "bootstrap.min.css").read_text(encoding="utf-8")
logo = base64.b64encode((WEB / "brasao_preto_vertical.svg").read_bytes()).decode()
def numero(valor):
    """Número com uma casa decimal e vírgula, como se escreve no Brasil."""
    return f"{valor:.1f}".replace(".", ",")
def simplificar(texto):
    """Minúsculas e sem acentos, para a busca não depender deles."""
    sem_acentos = ""
    for letra in unicodedata.normalize("NFKD", texto.lower()):
        if not unicodedata.combining(letra):
            sem_acentos += letra
    return sem_acentos
grupos = perfis_grupos.index.drop("Pará")
cores = {}
for posicao, grupo in enumerate(grupos):
    cores[grupo] = CORES[posicao % len(CORES)]
populacao = f'{indicadores["pop_total"].sum():,}'.replace(",", ".")
resumo = [(len(atribuicao), "municípios"), (len(grupos), "grupos"), (populacao, "habitantes")]
destaques = []
for valor, legenda in resumo:
    destaques.append(f'<div class="col-6 col-md-4"><div class="card shadow-sm h-100"><div class="card-body">'
                     f'<div class="numero-destaque">{valor}</div><div class="small text-body-secondary">{legenda}</div></div></div></div>')
cartoes = []
opcoes = ['<option value="">Todos os grupos</option>']
mediana_para = perfis_grupos.loc["Pará"]
for grupo in grupos:
    linha = perfis_grupos.loc[grupo]
    cor = cores[grupo]
    municipios = int(linha["municipios"])
    cartao = f'<div class="col-sm-6 col-xl-3"><div class="card cartao-grupo shadow-sm h-100" style="--cor: {cor}"><div class="card-body d-flex flex-column">'
    cartao += f'<span class="badge align-self-start mb-2" style="background: {cor}">{grupo}</span>'
    cartao += f'<p class="small text-body-secondary mb-1">{municipios} municípios · {numero(linha["populacao_pct"])}% da população</p>'
    cartao += f'<div class="progress mb-3" style="height: 6px" role="progressbar" aria-label="População do grupo" aria-valuenow="{linha["populacao_pct"]}" aria-valuemin="0" aria-valuemax="100">'
    cartao += f'<div class="progress-bar" style="width: {linha["populacao_pct"]}%; background: {cor}"></div></div>'
    cartao += '<ul class="list-unstyled small mb-3">'
    for variavel in variaveis_modelo:
        cartao += (f'<li class="d-flex justify-content-between gap-2"><span>{NOMES[variavel].replace(" (%)", "")}</span>'
                   f'<span class="text-nowrap"><strong>{numero(linha[variavel])}%</strong> '
                   f'<span class="text-body-secondary">({numero(mediana_para[variavel])}%)</span></span></li>')
    cartao += "</ul>"
    cartao += f'<button type="button" class="btn btn-sm btn-outline-secondary mt-auto" data-filtrar="{grupo}">Ver municípios</button></div></div></div>'
    cartoes.append(cartao)
    opcoes.append(f'<option value="{grupo}">{grupo} ({municipios} municípios)</option>')
tabela_municipios = atribuicao.join(indicadores[list(NOMES)].round(1))
tabela_municipios = tabela_municipios.sort_values("municipio", key=lambda nomes: nomes.str.normalize("NFKD"))
cabecalho = "<tr><th>Município</th><th>Grupo</th>"
for variavel in variaveis_modelo:
    cabecalho += f'<th class="text-end">{NOMES[variavel]}</th>'
cabecalho += "</tr>"
linhas = []
for codigo, municipio in tabela_municipios.iterrows():
    grupo = municipio["grupo"]
    busca = simplificar(f'{municipio["municipio"]} {codigo} {grupo}')
    linha = f'<tr data-grupo="{grupo}" data-busca="{escape(busca)}">'
    linha += f'<td><div class="fw-semibold">{escape(municipio["municipio"])}</div><div class="small text-body-secondary">{codigo}</div></td>'
    linha += f'<td><span class="badge" style="background: {cores[grupo]}">{grupo}</span></td>'
    for variavel in variaveis_modelo:
        linha += f'<td class="text-end">{numero(municipio[variavel])}</td>'
    linhas.append(linha + "</tr>")
tabela_csv = tabela_municipios.reset_index().rename(columns={"cod_mun": "Código IBGE", "municipio": "Município", "grupo": "Grupo"})
csv_texto = tabela_csv.rename(columns=NOMES).to_csv(index=False, sep=";", decimal=",")
csv_base64 = base64.b64encode(csv_texto.encode("utf-8-sig")).decode()

ESTILO = """
body { background: #f3f5f8; }
.marca { position: fixed; top: 50%; right: 0; height: 85vh; transform: translate(50%, -50%); opacity: 0.06; z-index: -1; pointer-events: none; }
.topo { background: linear-gradient(135deg, #0b2e4f, #1d5c8c); padding-bottom: 4.5rem; }
.projeto { letter-spacing: 0.15em; text-transform: uppercase; font-size: 0.85rem; opacity: 0.85; }
.destaques { margin-top: -3rem; }
.numero-destaque { font-size: 1.5rem; font-weight: 700; color: #0b2e4f; }
.cartao-grupo { border-top: 4px solid var(--cor); }
#municipios th { font-size: 0.8rem; }
#municipios td.text-end { white-space: nowrap; }
"""
SCRIPT = r"""
const POR_PAGINA = 5;
const linhas = Array.from(document.querySelectorAll("#municipios tbody tr"));
const busca = document.getElementById("busca");
const filtroGrupo = document.getElementById("filtro-grupo");
const paginacao = document.getElementById("paginacao");
const resumo = document.getElementById("resumo");
let pagina = 1;
function simplificar(texto) {
  return texto.toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g, "");
}
function filtradas() {
  const procurado = simplificar(busca.value.trim());
  return linhas.filter(function (linha) {
    const grupoCerto = filtroGrupo.value === "" || linha.dataset.grupo === filtroGrupo.value;
    return grupoCerto && linha.dataset.busca.includes(procurado);
  });
}
function botao(texto, numero, ativo, desativado) {
  const item = document.createElement("li");
  item.className = "page-item" + (ativo ? " active" : "") + (desativado ? " disabled" : "");
  const link = document.createElement("button");
  link.className = "page-link";
  link.textContent = texto;
  link.disabled = desativado;
  link.addEventListener("click", function () { pagina = numero; mostrar(); });
  item.appendChild(link);
  return item;
}
function mostrar() {
  const visiveis = filtradas();
  const totalPaginas = Math.max(1, Math.ceil(visiveis.length / POR_PAGINA));
  pagina = Math.min(pagina, totalPaginas);
  const inicio = (pagina - 1) * POR_PAGINA;
  for (const linha of linhas) linha.hidden = true;
  for (const linha of visiveis.slice(inicio, inicio + POR_PAGINA)) linha.hidden = false;
  if (visiveis.length === 0) {
    resumo.textContent = "Nenhum município encontrado";
  } else if (visiveis.length === 1) {
    resumo.textContent = "1 município encontrado";
  } else {
    resumo.textContent = "Mostrando " + (inicio + 1) + "–" + Math.min(inicio + POR_PAGINA, visiveis.length) + " de " + visiveis.length + " municípios";
  }
  paginacao.replaceChildren();
  paginacao.appendChild(botao("‹", pagina - 1, false, pagina === 1));
  for (let n = 1; n <= totalPaginas; n++) {
    if (n === 1 || n === totalPaginas || Math.abs(n - pagina) <= 1) {
      paginacao.appendChild(botao(String(n), n, n === pagina, false));
    } else if (n === pagina - 2 || n === pagina + 2) {
      paginacao.appendChild(botao("…", n, false, true));
    }
  }
  paginacao.appendChild(botao("›", pagina + 1, false, pagina === totalPaginas));
}
busca.addEventListener("input", function () { pagina = 1; mostrar(); });
filtroGrupo.addEventListener("change", function () { pagina = 1; mostrar(); });
for (const botaoGrupo of document.querySelectorAll("[data-filtrar]")) {
  botaoGrupo.addEventListener("click", function () {
    filtroGrupo.value = botaoGrupo.dataset.filtrar;
    busca.value = "";
    pagina = 1;
    mostrar();
    document.getElementById("consulta").scrollIntoView({ behavior: "smooth" });
  });
}
mostrar();
"""
LUPA = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="7" cy="7" r="5"/><line x1="11" y1="11" x2="15" y2="15"/></svg>'
partes = []
partes.append('<!doctype html><html lang="pt-BR" data-bs-theme="light"><head><meta charset="utf-8">')
partes.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
partes.append(f"<title>Saúde para o Bem Viver · Tipologia dos municípios do Pará</title><style>{bootstrap}</style><style>{ESTILO}</style></head><body>")
partes.append(f'<img class="marca" src="data:image/svg+xml;base64,{logo}" alt="">')
partes.append('<header class="topo text-white"><div class="container py-5">')
partes.append('<p class="projeto mb-2">Saúde para o Bem Viver</p>')
partes.append('<h1 class="display-6 fw-bold mb-2">Tipologia dos municípios do Pará</h1>')
partes.append('<p class="lead mb-0">Estrutura etária e saneamento básico · Censo Demográfico 2022</p></div></header>')
partes.append('<main class="container pb-5">')
partes.append('<div class="row g-3 destaques mb-4">' + "".join(destaques) + "</div>")
partes.append('<div class="row g-3 mb-2">' + "".join(cartoes) + "</div>")
partes.append('<p class="small text-body-secondary mb-4">Em cada grupo: mediana dos municípios do grupo e, entre parênteses, a mediana do Pará. Água e esgoto em % dos domicílios; idade em % da população.</p>')
partes.append('<section id="consulta" class="card shadow-sm"><div class="card-body">')
partes.append('<div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3"><h2 class="h5 mb-0">Consultar um município</h2>')
partes.append(f'<a class="btn btn-sm btn-outline-primary" download="tipologia_{nome}.csv" href="data:text/csv;base64,{csv_base64}">Baixar a tabela completa (CSV)</a></div>')
partes.append(f'<div class="row g-2 mb-3"><div class="col-md-8"><div class="input-group"><span class="input-group-text">{LUPA}</span>')
partes.append('<input id="busca" type="search" class="form-control" aria-label="Buscar município" placeholder="Nome do município ou código IBGE"></div></div>')
partes.append('<div class="col-md-4"><select id="filtro-grupo" class="form-select" aria-label="Filtrar por grupo">' + "".join(opcoes) + "</select></div></div>")
partes.append('<div class="table-responsive"><table id="municipios" class="table table-hover align-middle mb-3">')
partes.append(f"<thead>{cabecalho}</thead><tbody>" + "".join(linhas) + "</tbody></table></div>")
partes.append('<div class="d-flex flex-wrap justify-content-between align-items-center gap-2"><span id="resumo" class="small text-body-secondary"></span>')
partes.append('<nav aria-label="Páginas"><ul id="paginacao" class="pagination pagination-sm flex-wrap mb-0"></ul></nav></div></div></section>')
partes.append('<footer class="mt-5 small text-body-secondary"><p>Fonte: IBGE, Censo Demográfico 2022 (SIDRA, tabelas 9514, 6804, 6805 e 9923)</p></footer>')
partes.append(f"</main><script>{SCRIPT}</script></body></html>")
arquivo = SAIDA / f"tipologia_{nome}.html"
arquivo.write_text("\n".join(partes), encoding="utf-8")
print("Página salva em", arquivo)
