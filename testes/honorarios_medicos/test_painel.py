"""Tela do módulo Honorários Médicos (montada sem mostrar a janela).

Refeitos a partir dos testes das telas antigas (test_interface_apoio.py do Conciliações AMES:
test_config_lembra_honorarios, test_painel_honorarios_com_arquivos_reais,
test_config_lembra_honorarios_hospital_exemplo e test_painel_honorarios_hospital_exemplo_com_arquivos_reais), com as
mesmas verificações, mais as regras da Central (abas, aba lembrada, módulo independente). Todos usam um
%APPDATA% temporário e nunca abrem o Excel.
"""

from __future__ import annotations

import ast
import json

import pytest

from central import registro
from central.painel_abas import ABA_INSTRUCOES
from modulos.honorarios_medicos import MODULO, processamento
from modulos.honorarios_medicos.painel import ABA_AMES, ABA_HOSPITAL_EXEMPLO
from testes.conftest import PASTA_EXEMPLOS, RAIZ, esperar

PASTA_HONORARIOS = PASTA_EXEMPLOS / "honorarios_medicos" / "Exemplos_Honorarios"
PASTA_MODULO = RAIZ / "modulos" / "honorarios_medicos"


@pytest.fixture(autouse=True)
def appdata_temporario(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


def _sem_excel(painel, monkeypatch):
    painel.abertos = []
    monkeypatch.setattr(painel, "abrir", painel.abertos.append)   # nunca abre o Excel de verdade
    return painel


@pytest.fixture
def ames(criar_painel, monkeypatch):
    return _sem_excel(criar_painel(MODULO).ames, monkeypatch)


@pytest.fixture
def hospital_exemplo(criar_painel, monkeypatch):
    painel = criar_painel(MODULO)
    painel.abas.selecionar(ABA_HOSPITAL_EXEMPLO, avisar=True)
    return _sem_excel(painel.hospital_exemplo, monkeypatch)


def _textos(widget):
    """Todos os textos de rótulos dentro de um widget (para conferir o que a tela mostra)."""
    textos = []
    for filho in widget.winfo_children():
        try:
            texto = filho.cget("text")
        except Exception:
            texto = None
        if isinstance(texto, str):
            textos.append(texto)
        textos.extend(_textos(filho))
    return textos


# ---------------------------------------------------------------------------
# Módulo e arquitetura
# ---------------------------------------------------------------------------


def test_modulo_no_registro_na_secao_do_passivo():
    assert registro.SECAO_DO_MODULO["honorarios_medicos"] == "CONCILIAÇÕES · PASSIVO"
    carregado = next(m for m in registro.carregar_modulos() if m.chave == "honorarios_medicos")
    assert carregado.ok and carregado.info.nome == "Honorários Médicos"
    assert (RAIZ / "central" / "icones" / f"{carregado.info.icone}.png").exists()
    assert (PASTA_MODULO / "INSTRUCOES_DE_USO.md").exists()


def test_telas_so_usam_o_processamento():
    for nome in ("ames", "hospital_exemplo", "comum"):
        arvore = ast.parse((PASTA_MODULO / "telas" / f"{nome}.py").read_text(encoding="utf-8"))
        do_modulo = {no.module for no in ast.walk(arvore) if isinstance(no, ast.ImportFrom)
                     and no.module and no.module.startswith("modulos.")}
        assert do_modulo <= {"modulos.honorarios_medicos", "modulos.honorarios_medicos.processamento",
                             "modulos.honorarios_medicos.telas.comum"}, nome


def test_modulo_nao_importa_outro_modulo():
    """O que Honorários usa de Fornecedores está copiado na subpasta fornecedores/ do próprio módulo."""
    for arquivo in PASTA_MODULO.rglob("*.py"):
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if isinstance(no, ast.ImportFrom) and no.module and no.module.startswith("modulos."):
                assert no.module.startswith("modulos.honorarios_medicos"), (arquivo.name, no.module)


def test_copia_de_fornecedores_igual_a_do_modulo_fornecedores():
    """A subpasta fornecedores/ é cópia inteira (só os import mudam): se um lado mudar, o teste avisa, para a
    mudança ser pensada nos dois módulos."""
    for nome in ("avisos", "leitores", "modelos", "pareamento", "processar", "relatorio_excel"):
        original = (RAIZ / "modulos" / "conciliacao_fornecedores" / f"{nome}.py").read_text(encoding="utf-8")
        copia = (PASTA_MODULO / "fornecedores" / f"{nome}.py").read_text(encoding="utf-8")
        assert copia == original.replace("modulos.conciliacao_fornecedores.",
                                         "modulos.honorarios_medicos.fornecedores."), nome


# ---------------------------------------------------------------------------
# Abas e aba lembrada
# ---------------------------------------------------------------------------


def test_abas_do_modulo(criar_painel):
    painel = criar_painel(MODULO)
    assert list(painel.abas.botoes) == [ABA_AMES, ABA_HOSPITAL_EXEMPLO, ABA_INSTRUCOES]
    assert painel.aba_atual == ABA_AMES
    assert list(painel.paineis) == [ABA_AMES]                   # a outra só é montada quando abrir


def test_aba_lembrada_salva_e_le(tmp_path):
    assert processamento.ler_aba_lembrada(tmp_path) == processamento.ABA_AMES
    assert processamento.salvar_aba_lembrada(processamento.ABA_HOSPITAL_EXEMPLO, tmp_path)
    assert processamento.ler_aba_lembrada(tmp_path) == processamento.ABA_HOSPITAL_EXEMPLO
    processamento.salvar_aba_lembrada("qualquer", tmp_path)
    assert processamento.ler_aba_lembrada(tmp_path) == processamento.ABA_AMES


def test_aba_vem_do_conciliacoes_ames_so_enquanto_a_central_nao_guardou(tmp_path):
    antigo = tmp_path / "config.json"
    antigo.write_text(json.dumps({"cidade": "HONSC"}), encoding="utf-8")
    assert processamento.ler_aba_lembrada(tmp_path / "central", antigo) == processamento.ABA_HOSPITAL_EXEMPLO
    processamento.salvar_aba_lembrada(processamento.ABA_AMES, tmp_path / "central")
    assert processamento.ler_aba_lembrada(tmp_path / "central", antigo) == processamento.ABA_AMES
    antigo.write_text(json.dumps({"cidade": "HON"}), encoding="utf-8")       # último item: Honorários (AME)
    assert processamento.ler_aba_lembrada(tmp_path / "outra", antigo) == processamento.ABA_AMES


def test_abre_na_ultima_aba_e_lembra_a_troca(criar_painel):
    painel = criar_painel(MODULO)
    painel.abas.selecionar(ABA_HOSPITAL_EXEMPLO, avisar=True)         # como se o usuário clicasse
    assert processamento.ler_aba_lembrada() == processamento.ABA_HOSPITAL_EXEMPLO
    painel.abas.selecionar(ABA_INSTRUCOES, avisar=True)         # as instruções não contam
    assert processamento.ler_aba_lembrada() == processamento.ABA_HOSPITAL_EXEMPLO

    outro = criar_painel(MODULO)                                # abre de novo: na aba lembrada
    assert outro.aba_atual == ABA_HOSPITAL_EXEMPLO
    assert list(outro.paineis) == [ABA_HOSPITAL_EXEMPLO]


# ---------------------------------------------------------------------------
# Pasta lembrada, uma por aba (eram test_config_lembra_honorarios e _hospital_exemplo)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("aba", [processamento.ABA_AMES, processamento.ABA_HOSPITAL_EXEMPLO])
def test_pasta_lembrada_salva_e_le(tmp_path, aba):
    assert processamento.ler_pasta_lembrada(aba, tmp_path) == ""
    assert processamento.salvar_pasta_lembrada(aba, str(tmp_path), tmp_path)
    assert processamento.ler_pasta_lembrada(aba, tmp_path) == str(tmp_path)


def test_pastas_vem_do_conciliacoes_ames_so_enquanto_a_central_nao_guardou(tmp_path):
    antigo = tmp_path / "config.json"
    antigo.write_text(json.dumps({"pasta_honorarios": "C:/Hon/AME", "pasta_honorarios_hospital_exemplo": "C:/Hon/SC"}),
                      encoding="utf-8")
    central = tmp_path / "central"
    assert processamento.ler_pasta_lembrada(processamento.ABA_AMES, central, antigo) == "C:/Hon/AME"
    assert processamento.ler_pasta_lembrada(processamento.ABA_HOSPITAL_EXEMPLO, central, antigo) == "C:/Hon/SC"
    processamento.salvar_pasta_lembrada(processamento.ABA_AMES, "", central)
    assert processamento.ler_pasta_lembrada(processamento.ABA_AMES, central, antigo) == ""
    assert processamento.ler_pasta_lembrada(processamento.ABA_HOSPITAL_EXEMPLO, central, antigo) == "C:/Hon/SC"


def test_cada_aba_lembra_a_sua_pasta(criar_painel, tmp_path):
    pasta_ames, pasta_hospital_exemplo = tmp_path / "ames", tmp_path / "hospital_exemplo"
    pasta_ames.mkdir()
    pasta_hospital_exemplo.mkdir()
    painel = criar_painel(MODULO)
    assert not painel.ames.cartao_pasta.preenchido
    painel.ames.cartao_pasta.definir_caminhos([pasta_ames])
    painel.abas.selecionar(ABA_HOSPITAL_EXEMPLO, avisar=True)
    assert not painel.hospital_exemplo.cartao_pasta.preenchido
    painel.hospital_exemplo.cartao_pasta.definir_caminhos([pasta_hospital_exemplo])
    painel.ames.novo()                                          # "Limpar tudo" não esquece a pasta
    assert painel.ames.cartao_pasta.caminho == pasta_ames

    outro = criar_painel(MODULO)
    outro.abas.selecionar(ABA_AMES, avisar=True)
    assert outro.ames.cartao_pasta.caminho == pasta_ames
    assert outro.hospital_exemplo.cartao_pasta.caminho == pasta_hospital_exemplo


# ---------------------------------------------------------------------------
# Aba AMEs com os arquivos reais (era test_painel_honorarios_com_arquivos_reais)
# ---------------------------------------------------------------------------


def test_ames_com_arquivos_reais(ames, tmp_path):
    assert not ames.botao.habilitado
    pasta = PASTA_HONORARIOS / "set2026_CidadeDelta"
    if not pasta.exists():
        pytest.skip("exemplos/honorarios_medicos/Exemplos_Honorarios não existe")

    # no exemplo os nomes vieram trocados: "Rel HM.xls" é o balancete
    balancete, repasse = pasta / "Rel HM.xls", pasta / "Balancete (2).xls"
    ames.cartao_balancete.definir_caminhos([repasse])               # arquivo trocado
    assert ames.cartao_balancete.status_confirmacao == "erro"
    assert "Repasse médico" in ames.cartao_balancete.texto_confirmacao
    ames.cartao_balancete.definir_caminhos([balancete])
    assert ames.cartao_balancete.texto_confirmacao == \
        "AME - Cidade Delta · set/2026 · conta 2132 · 53 contas · R$ 366.298,38"
    assert not ames.botao.habilitado
    ames.cartao_repasse.definir_caminhos([repasse])
    assert ames.cartao_repasse.texto_confirmacao == \
        "AME - Cidade Delta · set/2026 · 70 repasses · 53 terceiros · R$ 366.298,38"
    assert ames.botao.habilitado

    resultado = processamento.processar_ames(balancete, repasse, pasta_destino=tmp_path)
    ames.mostrar_resultado(resultado)
    ames.update()
    assert ames.resultado.selo.cget("text") == "Concluído"
    textos = _textos(ames.resultado)
    assert "Médicos OK" in textos and "53" in textos
    assert "Retenções (bruto − líquido)" in textos and "10.486,25" in textos
    ames.novo()
    assert not any(c.preenchido for c in ames.cartoes_relatorios)


def test_ames_gerar_pela_tela_e_botoes_do_resultado(ames, tmp_path):
    pasta = PASTA_HONORARIOS / "set2026_CidadeDelta"
    if not pasta.exists():
        pytest.skip("exemplos/honorarios_medicos/Exemplos_Honorarios não existe")
    saida = tmp_path / "saida"
    saida.mkdir()
    ames.cartao_balancete.definir_caminhos([pasta / "Rel HM.xls"])
    ames.cartao_repasse.definir_caminhos([pasta / "Balancete (2).xls"])
    ames.cartao_pasta.definir_caminhos([saida])
    ames.processar()
    esperar(ames, lambda: not ames.ocupado)

    resultado = ames.resultado_conciliacao
    assert resultado.erro is None
    assert resultado.caminho_relatorio == saida / "Conciliacao_HonorariosMedicos_CidadeDelta_set2026.xlsx"
    botoes = {b.cget("text"): b for b in ames.resultado.rodape.winfo_children()}
    assert list(botoes)[:3] == ["Abrir planilha", "Abrir pasta", "Ver avisos"]
    botoes["Abrir planilha"].invoke()
    assert ames.abertos == [resultado.caminho_relatorio]
    botoes["Ver avisos"].invoke()
    assert ames.janela_avisos.texto.startswith("ARQUIVOS LIDOS\n•")
    ames.janela_avisos.destroy()


# ---------------------------------------------------------------------------
# Aba Hospital Exemplo com os arquivos reais (era test_painel_honorarios_hospital_exemplo_com_arquivos_reais)
# ---------------------------------------------------------------------------


def _esperar_previa(painel):
    esperar(painel, lambda: painel.previa is not None, limite_segundos=60)


def test_hospital_exemplo_com_arquivos_reais(hospital_exemplo, tmp_path, monkeypatch):
    assert not hospital_exemplo.botao.habilitado
    pasta = PASTA_HONORARIOS / "Conciliações Hospital Exemplo"
    if not pasta.exists():
        pytest.skip("exemplos/honorarios_medicos/Exemplos_Honorarios/Conciliações Hospital Exemplo não existe")

    # a janela do Windows é trocada por uma lista: cada "Adicionar arquivos" ACRESCENTA ao que já estava
    from central import componentes
    escolhas = [[pasta / "PJ" / "HM PJ Senior 09-2026.XLS"],
                [pasta / "PF" / nome for nome in ("Balancete PF 09-2026.xls", "HM PF Senior 09-2026.XLS",
                                                  "ok- Relatorio 6095 - Deslocamento - 09.26 - ok.pdf",
                                                  "ok- TASY - Remocao - 09.26 - ok.pdf")],
                [pasta / "PJ" / "Balancete PJ 09-2026.xls", pasta / "PJ" / "HM PJ Senior 09-2026.XLS"]]
    monkeypatch.setattr(componentes.filedialog, "askopenfilenames",
                        lambda **opcoes: tuple(str(c) for c in escolhas.pop(0)))
    cartao = hospital_exemplo.cartao_arquivos
    assert cartao.botao.cget("text") == "Adicionar arquivos"

    cartao.selecionar()                                    # só o HM PJ: falta o balancete → não deixa gerar
    _esperar_previa(hospital_exemplo)
    assert cartao.status_confirmacao == "erro" and "Falta o balancete" in cartao.texto_confirmacao
    assert not hospital_exemplo.botao.habilitado

    cartao.selecionar()                                    # + os da pasta PF: já tem balancete, pode gerar
    _esperar_previa(hospital_exemplo)
    assert len(hospital_exemplo.escolhidos) == 5
    assert cartao.status_confirmacao == "atencao"
    assert cartao.texto_confirmacao == "Balancete PF · HM PF e PJ Senior · 2 PDFs de repasse · Falta: balancete PJ"
    assert hospital_exemplo.botao.habilitado

    cartao.selecionar()                                    # + os da pasta PJ (o HM PJ repetido entra uma vez)
    _esperar_previa(hospital_exemplo)
    assert len(hospital_exemplo.escolhidos) == 6
    assert cartao.texto_confirmacao == "Balancete PF e PJ · HM PF e PJ Senior · 2 PDFs de repasse"
    assert cartao.status_confirmacao == "ok"
    assert cartao.botao.cget("text") == "Adicionar arquivos"

    resultado = processamento.processar_hospital_exemplo(hospital_exemplo.escolhidos, pasta_destino=tmp_path)
    hospital_exemplo.mostrar_resultado(resultado)
    hospital_exemplo.update()
    assert hospital_exemplo.resultado.selo.cget("text") == "Concluído"
    textos = _textos(hospital_exemplo.resultado)
    assert "Médicos OK" in textos and "365" in textos
    assert "PF (R$)" in textos and "PJ (R$)" in textos and "83.748,35" in textos
    hospital_exemplo.novo()
    assert not any(c.preenchido for c in hospital_exemplo.cartoes_relatorios)
    assert not hospital_exemplo.botao.habilitado


def test_hospital_exemplo_conferencia_antiga_e_ignorada(hospital_exemplo, tmp_path):
    """Trocar a escolha (ou limpar) enquanto a conferência roda: vale a da escolha mais nova."""
    arquivo = tmp_path / "anotacoes.txt"
    arquivo.write_text("não é relatório", encoding="utf-8")
    hospital_exemplo.cartao_arquivos.definir_caminhos([arquivo])
    assert hospital_exemplo.cartao_arquivos.texto_confirmacao == "Conferindo os arquivos..."
    assert not hospital_exemplo.botao.habilitado
    hospital_exemplo.novo()                                      # limpou antes de a conferência terminar
    import time

    fim = time.monotonic() + 5
    while time.monotonic() < fim:
        hospital_exemplo.update()
        time.sleep(0.05)
    assert hospital_exemplo.previa is None and not hospital_exemplo.cartao_arquivos.preenchido
    assert not hospital_exemplo.botao.habilitado


def test_hospital_exemplo_gerar_pela_tela(hospital_exemplo, tmp_path):
    pasta = PASTA_HONORARIOS / "Conciliações Hospital Exemplo"
    if not pasta.exists():
        pytest.skip("exemplos/honorarios_medicos/Exemplos_Honorarios/Conciliações Hospital Exemplo não existe")
    saida = tmp_path / "saida"
    saida.mkdir()
    hospital_exemplo.cartao_arquivos.definir_caminhos(sorted((pasta / "PF").iterdir()) + sorted((pasta / "PJ").iterdir()))
    _esperar_previa(hospital_exemplo)
    hospital_exemplo.cartao_pasta.definir_caminhos([saida])
    assert hospital_exemplo.botao.habilitado
    hospital_exemplo.processar()
    esperar(hospital_exemplo, lambda: not hospital_exemplo.ocupado)

    resultado = hospital_exemplo.resultado_conciliacao
    assert resultado.erro is None
    assert resultado.caminho_relatorio == saida / "Conciliacao_Honorarios_Medicos_PF_PJ_09_2026.xlsx"
    botoes = {b.cget("text"): b for b in hospital_exemplo.resultado.rodape.winfo_children()}
    botoes["Abrir planilha"].invoke()
    assert hospital_exemplo.abertos == [resultado.caminho_relatorio]
