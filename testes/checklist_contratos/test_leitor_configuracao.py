"""T2 — arquivos de configuração (seção 3.3) e relocalização da linha (K2, K3)."""

from __future__ import annotations

import pytest

from modulos.checklist_contratos.conferencia import localizar_linha
from modulos.checklist_contratos.leitor_checklist import ler_checklist
from modulos.checklist_contratos.leitor_configuracao import ler_configuracao
from modulos.checklist_contratos.modelos import ErroLeitura
from testes.checklist_contratos.conftest import escrever_checklist, exemplos

TITULOS_REGRAS = '"Aba";"Linha";"Fornecedor_Planilha";"Descricao_Planilha";"Contas";"Busca_Fornecedor";' \
                 '"Busca_Descricao";"Excluir";"Selecao";"Tipo";"Obs"'


def _escrever(pasta, nome, linhas):
    (pasta / nome).write_text("\n".join(linhas) + "\n", encoding="utf-8-sig")


def _config(tmp_path, regras):
    _escrever(tmp_path, "regras.csv", [TITULOS_REGRAS] + regras)
    return ler_configuracao(tmp_path)


def test_t2_coluna_centro_custo_opcional(tmp_path):
    _escrever(tmp_path, "regras.csv", [TITULOS_REGRAS + ';"Centro_Custo"',
                                       "SC;2;F;D;30223;locadora;;;;auto;;engenharia clinica",
                                       "SC;3;F;D;30223;locadora;;;;auto;;"])
    com, sem = ler_configuracao(tmp_path).regras
    assert com.centro_custo.search("engenharia clinica") and sem.centro_custo is None
    # arquivo sem a coluna continua valendo
    assert _config(tmp_path, ["SC;2;F;D;30223;locadora;;;;auto;"]).regras[0].centro_custo is None


def test_t2_regras(tmp_path):
    configuracao = _config(tmp_path, [
        'SC;2;Fornecedor Exemplo Ltda;Licença de Sistema;30037 / 30081;exemplo|outro nome;'
        'licen;devolucao;maior;auto;"obs; com ponto e vírgula"',
        'cmd;5;Energia Exemplo;Energia;30041/30089;^energia;;;;Manual;',
    ])
    assert configuracao.avisos == []
    primeira, segunda = configuracao.regras
    assert (primeira.aba, primeira.linha, primeira.contas, primeira.selecao, primeira.tipo, primeira.obs) == \
        ("SC", 2, ("30037", "30081"), "maior", "auto", "obs; com ponto e vírgula")
    assert primeira.busca_fornecedor.search("nf de outro nome ltda")
    assert primeira.busca_fornecedor.search("EXEMPLO")                    # sem diferença de maiúsculas
    assert primeira.busca_descricao.search("licenca") and primeira.excluir.search("devolucao nf")
    assert (segunda.aba, segunda.tipo, segunda.busca_descricao, segunda.excluir) == ("CMD", "manual", None, None)
    assert primeira.linha_arquivo == 2 and segunda.linha_arquivo == 3


def test_t2_linha_com_problema_e_pulada_com_aviso(tmp_path):
    configuracao = _config(tmp_path, [
        "XX;2;F;D;30091;exemplo;;;;auto;",          # aba desconhecida
        "SC;dois;F;D;30091;exemplo;;;;auto;",       # linha não é número
        "SC;4;F;D;30091;(sem fechar;;;;auto;",      # expressão inválida
        "SC;5;F;D;30091;exemplo;;;;talvez;",        # tipo desconhecido
        "SC;6;F;D;30091;exemplo;;;meio;auto;",      # seleção desconhecida
        "SC;7;F;D;30091;;;;;auto;",                 # sem Busca_Fornecedor
        "SC;8;F;D;30091;;;;;ignorar;",              # ignorada pode ficar sem busca
        "SC;9;F;D;30091;exemplo;;;;auto;",
    ])
    assert [r.linha for r in configuracao.regras] == [8, 9]
    assert [a.origem for a in configuracao.avisos] == [f"regras.csv linha {n}" for n in range(2, 8)]
    assert "expressão válida" in configuracao.avisos[2].mensagem


def test_t2_coluna_faltando_ou_arquivo_faltando(tmp_path):
    with pytest.raises(ErroLeitura, match="regras.csv"):
        ler_configuracao(tmp_path)
    (tmp_path / "regras.csv").write_text("Aba;Linha;Contas\n", encoding="utf-8")
    with pytest.raises(ErroLeitura, match="Busca_Fornecedor"):
        ler_configuracao(tmp_path)


def test_t2_arquivos_aposentados_viram_aviso(tmp_path):
    # destinatarios_extras.csv e redirecionamentos.csv deram lugar aos códigos do Check list (23/10/2026)
    _escrever(tmp_path, "destinatarios_extras.csv", ["Responsavel;Email;Obs", "*;todos@exemplo.org.br;"])
    configuracao = _config(tmp_path, ["SC;2;F;D;30091;exemplo;;;;auto;"])
    assert len(configuracao.regras) == 1
    assert [a.origem for a in configuracao.avisos] == ["destinatarios_extras.csv"]
    assert "não é mais usado" in configuracao.avisos[0].mensagem


# ---------------------------------------------------------------------------
# K2 / K3
# ---------------------------------------------------------------------------

LINHAS_SC = [
    [30108, "Mensalidades", None, "Confederação Exemplo", None, "Mensalidade CMB", "Ana"],
    [30091, "Software", None, "Fornecedor Exemplo Ltda", None, "Licença de Sistema", "Ana"],
]


def _k3(tmp_path, regra_csv):
    checklist = ler_checklist(escrever_checklist(tmp_path / "chk.xlsx", linhas_sc=LINHAS_SC), 2026, 10)
    configuracao = _config(tmp_path, [regra_csv])
    return localizar_linha(configuracao.regras[0], checklist.abas["SC"])


def test_k3_linha_no_lugar_certo(tmp_path):
    assert _k3(tmp_path, "SC;3;Fornecedor Exemplo Ltda;Licença de Sistema;30091;exemplo;;;;auto;") == (3, None)


def test_k3_linha_que_mudou_de_lugar(tmp_path):
    linha, aviso = _k3(tmp_path, "SC;2;FORNECEDOR EXEMPLO LTDA;Licenca  de sistema;30091;exemplo;;;;auto;")
    assert linha == 3
    assert aviso.origem == "regra SC linha 2" and "agora está na linha 3" in aviso.mensagem


def test_k3_regra_que_some_vira_aviso(tmp_path):
    # a descrição foi corrigida na planilha (ex.: "CBM" -> "CMB") e a regra ainda tem a antiga
    linha, aviso = _k3(tmp_path, "SC;2;Confederação Exemplo;Mensalidade CBM;30108;confedera;;;;auto;")
    assert linha is None and "regra pulada" in aviso.mensagem


def test_k3_regra_sem_texto_da_planilha_usa_a_linha(tmp_path):
    assert _k3(tmp_path, "SC;2;;;30108;confedera;;;;auto;") == (2, None)


def test_t2_configuracao_viva_e_lida_sem_avisos():
    # a pasta config\ muda quando o usuário edita a configuração: só precisa continuar legível
    configuracao = ler_configuracao(exemplos("config"))
    assert all("não é mais usado" in a.mensagem for a in configuracao.avisos)     # só os aposentados
    assert configuracao.regras


def test_t2_configuracao_do_gabarito_com_check_list_real():
    configuracao = ler_configuracao(exemplos("config_gabarito_22-10-2026"))
    assert [a.origem for a in configuracao.avisos] == ["destinatarios_extras.csv", "redirecionamentos.csv"]
    assert len(configuracao.regras) == 158
    assert sum(1 for r in configuracao.regras if r.aba == "SC") == 141
    for mes in ("2026-09", "2026-10"):
        checklist = ler_checklist(exemplos(mes) / "Check list 2026.xlsx", 2026, int(mes[-2:]))
        for regra in configuracao.regras:
            assert localizar_linha(regra, checklist.abas[regra.aba]) == (regra.linha, None)
