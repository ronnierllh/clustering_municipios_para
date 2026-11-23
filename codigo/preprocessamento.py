"""Pré-processamento, tabelas 6804, 6805, 9514 e 9923 do SIDRA"""
import csv
from itertools import combinations
from pathlib import Path
import pandas as pd

BRUTOS = Path("dados") / "originais"
SAIDA = Path("dados") / "saidas"
FONTES_ADEQUADAS = ["Rede geral de distribuição", "Poço profundo ou artesiano", "Poço raso, freático ou cacimba",
                    "Fonte, nascente ou mina", "Água da chuva armazenada"]
FONTES_SEM_ATENDIMENTO = ["Rios, açudes, córregos, lagos e igarapés", "Outra"]
ESGOTO_ADEQUADO = ["Rede geral ou pluvial", "Fossa séptica ou fossa filtro ligada à rede",
                   "Fossa séptica ou fossa filtro não ligada à rede"]
ESGOTO_PRECARIO = ["Fossa rudimentar ou buraco"]
ESGOTO_SEM_ATENDIMENTO = ["Vala", "Rio, lago, córrego ou mar", "Outra forma", "Não tinham banheiro nem sanitário"]

def ler_tabela(nome_arquivo, primeira_numerica):
    """Le um CSV do SIDRA e devolve as linhas com dados"""
    with open(BRUTOS / nome_arquivo, encoding="utf-8-sig", newline="") as arquivo:
        linhas = list(csv.reader(arquivo, delimiter=";"))
    cabecalhos = []
    dados = []
    for linha in linhas:
        if linha and linha[0] == "Cód.":
            cabecalhos.append(linha)
        if linha and linha[0].isdigit() and linha[0].startswith("15"):
            dados.append(linha)
    tabela = pd.DataFrame(dados, columns=cabecalhos[-1])
    for coluna in tabela.columns[primeira_numerica:]:
        tabela[coluna] = tabela[coluna].replace("-", "0").astype(int)
    tabela["Município"] = tabela["Município"].str.replace(" (PA)", "", regex=False)
    return tabela

idade = ler_tabela("censo2022_9514_idade_para.csv", 3)
agua = ler_tabela("censo2022_6804_agua_para.csv", 3)
esgoto = ler_tabela("censo2022_6805_esgoto_para.csv", 2).set_index("Cód.")
situacao = ler_tabela("censo2022_9923_situacao_para.csv", 2).set_index("Cód.")

forma = idade["Forma de declaração da idade"]
idade_total = idade[forma == "Total"].set_index("Cód.")
idade_presumida = idade[forma == "Idade presumida"].set_index("Cód.")
canalizacao = agua["Existência de canalização de água"]
agua_total = agua[canalizacao == "Total"].set_index("Cód.")
agua_dentro = agua[canalizacao == "Canalizada até dentro da casa, apartamento ou habitação"].set_index("Cód.")

GRUPOS_IDADE = list(idade_total.columns[3:])
FONTES = list(agua_total.columns[3:])
CATEGORIAS_ESGOTO = list(esgoto.columns[3:])
for tabela in [idade_total, idade_presumida, agua_total, agua_dentro, esgoto, situacao]:
    assert len(tabela) == 144 and set(tabela.index) == set(esgoto.index), "faltam municípios"
assert (idade_total[GRUPOS_IDADE].sum(axis=1) == idade_total["Total"]).all(), "idades não somam o total"
assert (agua_total[FONTES].sum(axis=1) == agua_total["Total"]).all(), "fontes de água não somam o total"
assert (esgoto[CATEGORIAS_ESGOTO].sum(axis=1) == esgoto["Total"]).all(), "categorias de esgoto não somam o total"
assert (agua_total["Total"] == esgoto["Total"]).all(), "domicílios diferentes entre água e esgoto"
assert (idade_total["Total"] == situacao["Total"]).all(), "população diferente entre idade e situação"
print("Controles: 144 municípios e todas as somas conferem")

GRUPOS_60_MAIS = GRUPOS_IDADE[12:]
agua_adequada = agua_dentro[FONTES_ADEQUADAS].sum(axis=1)
agua_sem = agua_total[FONTES_SEM_ATENDIMENTO].sum(axis=1)
agua_precaria = agua_total[FONTES_ADEQUADAS].sum(axis=1) - agua_adequada + agua_total["Carro-pipa"]
assert (agua_adequada + agua_precaria + agua_sem == agua_total["Total"]).all(), "classificação da água incompleta"

domicilios = esgoto["Total"]
populacao = idade_total["Total"]
indicadores = pd.DataFrame({
    "municipio": idade_total["Município"],
    "pop_total": populacao,
    "dom_total": domicilios,
    "pop_0a4_pct": 100 * idade_total["0 a 4 anos"] / populacao,
    "pop_60m_pct": 100 * idade_total[GRUPOS_60_MAIS].sum(axis=1) / populacao,
    "agua_adeq_pct": 100 * agua_adequada / domicilios,
    "agua_prec_pct": 100 * agua_precaria / domicilios,
    "agua_sem_pct": 100 * agua_sem / domicilios,
    "esg_adeq_pct": 100 * esgoto[ESGOTO_ADEQUADO].sum(axis=1) / domicilios,
    "esg_prec_pct": 100 * esgoto[ESGOTO_PRECARIO].sum(axis=1) / domicilios,
    "esg_sem_pct": 100 * esgoto[ESGOTO_SEM_ATENDIMENTO].sum(axis=1) / domicilios,
    "idade_pres_pct": 100 * idade_presumida["Total"] / populacao,
    "rural_pct": 100 * situacao["Rural"] / situacao["Total"],
})
indicadores.index.name = "cod_mun"
print(indicadores.describe().round(1).T[["mean", "std", "min", "50%", "max"]])

def par_menos_redundante(dados, colunas):
    """Devolve o par menos correlacionado (Spearman)"""
    matriz_correlacoes = dados[colunas].corr(method="spearman").abs()
    correlacoes_por_par = {}
    for coluna_a, coluna_b in combinations(colunas, 2):
        correlacao_par = matriz_correlacoes.loc[coluna_a, coluna_b]
        correlacoes_por_par[(coluna_a, coluna_b)] = correlacao_par
    par_menos_correlacionado = min(correlacoes_por_par, key=correlacoes_por_par.get)
    return list(par_menos_correlacionado)
print("Água:")
par_agua = par_menos_redundante(indicadores, ["agua_adeq_pct", "agua_prec_pct", "agua_sem_pct"])
print("Esgoto:")
par_esgoto = par_menos_redundante(indicadores, ["esg_adeq_pct", "esg_prec_pct", "esg_sem_pct"])
VARIAVEIS_MODELO = ["pop_0a4_pct", "pop_60m_pct"] + par_agua + par_esgoto

indicadores.to_csv(SAIDA / "indicadores_municipio.csv")
indicadores[VARIAVEIS_MODELO].to_csv(SAIDA / "matriz_modelo.csv")

