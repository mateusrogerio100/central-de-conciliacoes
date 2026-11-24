"""Testes das peças visuais (central/componentes.py), montadas sem mostrar a janela."""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk
import pytest

from central import componentes as c
from central import tema
from testes.conftest import abrir_janela_ctk


@pytest.fixture(scope="module")
def raiz():
    janela = abrir_janela_ctk()
    yield janela
    janela.destroy()


@pytest.fixture
def pai(raiz):
    frame = ctk.CTkFrame(raiz)
    frame.pack()
    yield frame
    frame.destroy()


# ---------------------------------------------------------------------------
# CartaoArquivo
# ---------------------------------------------------------------------------


def test_cartao_arquivo_sem_arquivo(pai):
    cartao = c.CartaoArquivo(pai, "Balancete")
    assert not cartao.preenchido and cartao.caminho is None
    assert cartao.texto_confirmacao == "Nenhum arquivo selecionado"
    assert cartao.botao.cget("text") == "Selecionar"


def test_cartao_pasta_sem_pasta(pai):
    assert c.CartaoArquivo(pai, "Extratos", tipo="pasta").texto_confirmacao == "Nenhuma pasta selecionada"


def test_cartao_arquivo_com_arquivo_e_confirmacao(pai):
    avisados = []
    cartao = c.CartaoArquivo(pai, "Balancete", ao_mudar=avisados.append)

    cartao.definir_caminhos(r"C:\dados\Balancete.xlsx")

    assert cartao.caminho == Path(r"C:\dados\Balancete.xlsx")
    assert cartao.texto_nome == "Balancete.xlsx"
    assert cartao.botao.cget("text") == "Trocar"
    assert avisados == [[Path(r"C:\dados\Balancete.xlsx")]]   # o módulo é avisado para conferir o arquivo

    cartao.definir_confirmacao("Mês de referência 08/2026", "ok")
    assert cartao.texto_confirmacao == "Mês de referência 08/2026"
    assert cartao.rotulo_confirmacao.cget("text_color") == tema.COR_OK
    cartao.definir_confirmacao("Mês diferente", "atencao")
    assert cartao.rotulo_confirmacao.cget("text_color") == tema.COR_ATENCAO
    cartao.definir_confirmacao("Não é um balancete", "erro")
    assert cartao.rotulo_confirmacao.cget("text_color") == tema.COR_ERRO


def test_cartao_mostra_a_barrinha_enquanto_le(pai):
    cartao = c.CartaoArquivo(pai, "Movimento", tipo="pasta")
    cartao.definir_caminhos(r"C:\dados\movimento")
    assert not cartao.carregando
    cartao.definir_carregando("Lendo o movimento...")
    assert cartao.carregando and cartao.texto_confirmacao == "Lendo o movimento..."
    assert cartao.status_confirmacao is None
    cartao.definir_confirmacao("22 arquivos", "ok")                  # terminou: a barrinha some
    assert not cartao.carregando and cartao.texto_confirmacao == "22 arquivos"
    cartao.definir_carregando("Lendo de novo...")
    cartao.definir_caminhos(r"C:\dados\outro")                       # trocou a pasta: some também
    assert not cartao.carregando


def test_cartao_varios_arquivos(pai):
    cartao = c.CartaoArquivo(pai, "Planilhas", tipo="arquivos")
    cartao.definir_caminhos(["a.xlsx", "b.xlsx", "c.xlsx", "d.xlsx", "e.xlsx"], avisar=False)
    assert len(cartao.caminhos) == 5
    assert cartao.texto_nome == "a.xlsx\nb.xlsx\nc.xlsx\ne mais 2"


def test_cartao_pasta_inicial_vai_para_o_seletor(pai, tmp_path, monkeypatch):
    from tkinter import filedialog

    chamadas = []
    monkeypatch.setattr(filedialog, "askopenfilename", lambda **opcoes: chamadas.append(opcoes) or "")
    cartao = c.CartaoArquivo(pai, "Lote")
    cartao.selecionar()
    assert "initialdir" not in chamadas[-1]                    # sem pasta: o padrão do Windows
    cartao.pasta_inicial = tmp_path
    cartao.selecionar()
    assert chamadas[-1]["initialdir"] == str(tmp_path)
    cartao.pasta_inicial = tmp_path / "apagada"                 # pasta que não existe mais: ignora
    cartao.selecionar()
    assert "initialdir" not in chamadas[-1]
    assert not cartao.preenchido                                # cancelou o seletor: nada muda


def test_cartao_limpar(pai):
    cartao = c.CartaoArquivo(pai, "Balancete")
    cartao.definir_caminhos("x.xlsx", avisar=False)
    cartao.limpar()
    assert not cartao.preenchido and cartao.botao.cget("text") == "Selecionar"


def test_cartao_tipo_invalido(pai):
    with pytest.raises(ValueError):
        c.CartaoArquivo(pai, "X", tipo="planilha")


# ---------------------------------------------------------------------------
# Botões, campo e números
# ---------------------------------------------------------------------------


def test_botao_principal_habilitar(pai):
    botao = c.BotaoPrincipal(pai, "Processar", icone="seta_direita")
    assert botao.habilitado
    botao.habilitar(False)
    assert not botao.habilitado and botao.cget("fg_color") == tema.COR_PRINCIPAL_SUAVE
    botao.habilitar(True)
    assert botao.habilitado and botao.cget("fg_color") == tema.COR_PRINCIPAL


def test_botao_secundario(pai):
    botao = c.BotaoSecundario(pai, "Ver avisos", icone="olho")
    botao.habilitar(False)
    assert not botao.habilitado


def test_campo_rotulado(pai):
    mudancas = []
    campo = c.CampoRotulado(pai, "Mês de referência", texto_inicial="08/2026", ao_mudar=mudancas.append)
    assert campo.valor() == "08/2026"
    campo.definir(" 09/2026 ")
    assert campo.valor() == "09/2026"
    assert mudancas[-1] == "09/2026"


def test_grupo_de_numeros(pai):
    grupo = c.GrupoNumeros(pai, [(42, "contas preenchidas"), (3, "com diferença", "atencao"), (5, "avisos", "erro")])
    assert [b.rotulo_numero.cget("text") for b in grupo.blocos] == ["42", "3", "5"]
    grupo.blocos[1].atualizar(0, "com diferença", tom="ok")
    assert grupo.blocos[1].rotulo_numero.cget("text_color") == tema.COR_OK


def test_tom_desconhecido(pai):
    with pytest.raises(ValueError, match="Tom desconhecido"):
        c.NumeroResumo(pai, 1, "x", tom="roxo")


def test_selo_status(pai):
    selo = c.SeloStatus(pai, "Concluído", "ok")
    selo.atualizar("ERRO", "erro")
    assert selo.cget("text") == "ERRO" and selo.cget("fg_color") == tema.COR_ERRO_SUAVE


# ---------------------------------------------------------------------------
# Tabela, conferência, estados do resultado
# ---------------------------------------------------------------------------


def test_tabela_simples(pai):
    tabela = c.TabelaSimples(pai, [c.Coluna("Aba", peso=2), c.Coluna("Contas", numero=True)],
                             [("Federal", 12), ("Estadual", 18)])
    assert tabela.linhas == [("Federal", 12), ("Estadual", 18)]
    separadores = [w for w in tabela.winfo_children() if isinstance(w, c.Separador)]
    assert len(separadores) == 2                          # um antes de cada linha
    tabela.definir_linhas([("Municipal", 7)])
    assert tabela.linhas == [("Municipal", 7)]
    assert len([w for w in tabela.winfo_children() if isinstance(w, c.Separador)]) == 1


def test_separador_troca_de_cor_com_o_modo(pai):
    separador = c.Separador(pai)
    separador._ao_mudar_modo("Light")
    assert separador.cget("bg") == tema.COR_BORDA[0]
    separador._ao_mudar_modo("Dark")
    assert separador.cget("bg") == tema.COR_BORDA[1]


@pytest.mark.parametrize("status", ["ok", "atencao", "erro"])
def test_linha_conferencia(pai, status):
    linha = c.LinhaConferencia(pai, "Soma dos bens = total do relatório", status, valor="1.234,56")
    assert linha.status == status


def test_cartao_resultado_estados(pai):
    resultado = c.CartaoResultado(pai)

    resultado.mostrar_vazio()
    assert resultado.estado == "vazio" and not resultado.rodape.winfo_manager()

    barra = resultado.mostrar_andamento("Lendo o balancete...")
    assert resultado.estado == "andamento" and resultado.barra is barra
    barra.atualizar("Lendo o patrimônio...", 0.4)
    assert barra.texto == "Lendo o patrimônio..." and barra.fracao == 0.4
    barra.atualizar(None, None)                            # sem porcentagem: barra em movimento
    assert barra.texto == "Lendo o patrimônio..." and barra.fracao is None
    barra.atualizar("Concluído.", 1.5)                     # fora da faixa: limitado a 1
    assert barra.barra.get() == pytest.approx(1.0)

    area = resultado.mostrar_conteudo()
    resultado.definir_selo("Concluído", "ok")
    assert resultado.estado == "concluido" and resultado.barra is None
    assert area.winfo_children() == []                     # área limpa para o módulo preencher
    assert resultado.rodape.winfo_manager() == "pack"
    assert resultado.selo.cget("text") == "Concluído"
    resultado.mostrar_vazio()
    assert resultado.selo is None


def test_cartao_botao_limpar(pai, tmp_path):
    mudancas = []
    cartao = c.CartaoArquivo(pai, "Extratos", tipo="arquivos", ao_mudar=mudancas.append)
    assert not cartao.mostra_limpar                         # nada escolhido: sem "Limpar"
    cartao.definir_caminhos([tmp_path / "a.pdf", tmp_path / "b.pdf"])
    assert cartao.mostra_limpar and cartao.botao.cget("text") == "Trocar"
    cartao.botao_limpar.invoke()
    assert not cartao.preenchido and not cartao.mostra_limpar
    assert cartao.texto_confirmacao == "Nenhum arquivo selecionado"
    assert mudancas[-1] == []                               # o módulo é avisado, como numa escolha
    assert cartao.botao.cget("text") == "Selecionar"


def test_limpar_do_novo_nao_avisa_o_modulo(pai, tmp_path):
    mudancas = []
    cartao = c.CartaoArquivo(pai, "Balancete", ao_mudar=mudancas.append)
    cartao.definir_caminhos(tmp_path / "a.xlsx", avisar=False)
    cartao.limpar()
    assert mudancas == [] and not cartao.mostra_limpar


def test_campo_com_lista(pai):
    mudancas = []
    campo = c.CampoComLista(pai, "CNPJ do tomador", ["98765432000198", "98765432000945"],
                            ao_mudar=mudancas.append)
    assert campo.valor() == ""                             # não escolhe sozinho o 1º da lista
    assert campo.opcoes == ["98765432000198", "98765432000945"]
    campo.definir(" 98765432000198 ")
    assert campo.valor() == "98765432000198" and mudancas[-1] == "98765432000198"
    campo.definir_opcoes(["1"])
    assert campo.opcoes == ["1"]


def test_seletor_de_opcoes(pai):
    escolhas = []
    seletor = c.SeletorOpcoes(pai, "Tipo da declaração", ["Normal", "Complementar"],
                              ao_mudar=escolhas.append)
    assert seletor.valor is None                           # pode começar sem nenhuma marcada
    seletor.botoes["Complementar"].invoke()
    assert seletor.valor == "Complementar" and escolhas == ["Complementar"]
    assert seletor.botoes["Complementar"].cget("fg_color") == tema.COR_PRINCIPAL_SUAVE
    assert seletor.botoes["Normal"].cget("fg_color") == tema.COR_SUPERFICIE
    seletor.selecionar(None)                               # "Novo" desmarca
    assert seletor.valor is None and escolhas == ["Complementar"]
    with pytest.raises(ValueError):
        seletor.selecionar("Outra")


def test_cabecalho_e_layout(pai):
    cabecalho = c.CabecalhoModulo(pai, "Conciliações / Bancos", "Conciliação Bancária", "Compara saldos.")
    assert cabecalho.rotulo_titulo.cget("text") == "Conciliação Bancária"
    layout = c.LayoutDuasColunas(pai)
    assert layout.esquerda.winfo_exists() and layout.direita.winfo_exists()


def test_estado_vazio(pai):
    vazio = c.EstadoVazio(pai, "Nenhum resultado ainda", "Selecione os arquivos.")
    assert vazio.rotulo_titulo.cget("text") == "Nenhum resultado ainda"


# ---------------------------------------------------------------------------
# Peças trazidas do Conciliações AMES
# ---------------------------------------------------------------------------


def test_cartao_que_acumula_vai_somando_os_arquivos(pai, monkeypatch):
    from tkinter import filedialog

    escolhas = iter([("C:/PF/balancete.xls", "C:/PF/hm.XLS"), ("C:/PJ/balancete.xls", "C:/PF/hm.XLS")])
    monkeypatch.setattr(filedialog, "askopenfilenames", lambda **_: next(escolhas))
    recebidos = []
    cartao = c.CartaoArquivo(pai, "Relatórios do mês", tipo="arquivos", acumular=True, ao_mudar=recebidos.append)
    assert cartao.botao.cget("text") == "Adicionar arquivos"

    cartao.selecionar()
    cartao.selecionar()                                    # o repetido entra uma vez só
    assert [p.as_posix() for p in cartao.caminhos] == ["C:/PF/balancete.xls", "C:/PF/hm.XLS", "C:/PJ/balancete.xls"]
    assert cartao.botao.cget("text") == "Adicionar arquivos" and len(recebidos) == 2
    cartao.limpar_pelo_usuario()
    assert cartao.caminhos == []


def test_acumular_so_vale_para_varios_arquivos(pai):
    assert not c.CartaoArquivo(pai, "Balancete", acumular=True).acumular


def test_quebra_de_linha_ignora_diferencas_pequenas(pai):
    rotulo = ctk.CTkLabel(pai, text="Com diferença ou sem par", wraplength=100)
    c._quebrar_em(rotulo, 100 + c.TOLERANCIA_QUEBRA)
    assert rotulo.cget("wraplength") == 100
    c._quebrar_em(rotulo, 100 + c.TOLERANCIA_QUEBRA + 1)
    assert rotulo.cget("wraplength") == 100 + c.TOLERANCIA_QUEBRA + 1


def test_quadros_de_numeros_nao_entram_em_ciclo_na_janela_minima(raiz):
    # na tela de Rescisões do Conciliações AMES (2.4.0) os 3 quadros se requebravam sem fim e o programa travava
    raiz.deiconify()
    raiz.geometry("420x300")
    frame = ctk.CTkFrame(raiz, width=330)
    frame.pack(fill="x")
    grupo = c.GrupoNumeros(frame, [(105, "Pagamentos achados"), (3, "Com diferença ou sem par", "atencao"),
                                   (12345, "Linhas na conciliação")])
    grupo.pack(fill="x")
    chamadas = {"n": 0}
    original = c._quebrar_em

    def contar(rotulo, largura):
        chamadas["n"] += 1
        original(rotulo, largura)

    c._quebrar_em = contar
    try:
        for _ in range(60):
            raiz.update()
    finally:
        c._quebrar_em = original
        frame.destroy()
        raiz.withdraw()
    assert chamadas["n"] < 60


def test_rodape_da_planilha(pai, tmp_path):
    rodape = ctk.CTkFrame(pai)
    cliques = []
    c.botoes_da_planilha(rodape, tmp_path / "Conciliacao.xlsx", lambda: cliques.append("planilha"),
                         lambda: cliques.append("pasta"), lambda: cliques.append("avisos"))
    botoes = {b.cget("text"): b for b in rodape.winfo_children()}
    assert list(botoes) == ["Abrir planilha", "Abrir pasta", "Ver avisos"]
    assert botoes["Abrir planilha"].habilitado
    for botao in botoes.values():
        botao.invoke()
    assert cliques == ["planilha", "pasta", "avisos"]

    c.botoes_da_planilha(rodape, None, lambda: None, lambda: None, lambda: None)   # sem planilha gravada
    assert not next(b for b in rodape.winfo_children() if b.cget("text") == "Abrir planilha").habilitado


def test_rotulo_arquivo_salvo(pai, tmp_path):
    area = ctk.CTkFrame(pai)
    c.rotulo_arquivo_salvo(area, None)
    assert area.winfo_children() == []
    c.rotulo_arquivo_salvo(area, tmp_path / "Conciliacao_Fornecedores_CidadeDelta_set2026.xlsx")
    assert area.winfo_children()[0].cget("text") == "Salvo como\nConciliacao_Fornecedores_CidadeDelta_set2026.xlsx"


def test_janela_de_texto(raiz):
    janela = c.JanelaTexto(raiz, "Avisos da conferência", "Avisos", ["ARQUIVOS LIDOS", "• a.csv: OK"])
    try:
        assert janela.title() == "Avisos da conferência"
        assert janela.texto == "ARQUIVOS LIDOS\n• a.csv: OK"
    finally:
        janela.destroy()


# ---------------------------------------------------------------------------
# Janela mínima (Etapa 9 da unificação): nada cortado, nenhuma palavra quebrada no meio
# ---------------------------------------------------------------------------


def _na_largura(raiz, largura: int):
    raiz.deiconify()
    raiz.geometry(f"{largura + 40}x400")
    frame = ctk.CTkFrame(raiz, width=largura, fg_color="transparent")
    frame.pack(fill="x", padx=20)
    return frame


def _atualizar(raiz, vezes: int = 30) -> None:
    for _ in range(vezes):
        raiz.update()


def test_quadro_de_numeros_nunca_quebra_palavra_no_meio(raiz):
    # "Não encontrado s" na tela de Rescisões, na janela mínima
    frame = _na_largura(raiz, 290)
    try:
        grupo = c.GrupoNumeros(frame, [(89, "Pagamentos achados", "ok"), (0, "Valores diferentes", "ok"),
                                       (3, "Não encontrados", "atencao")])
        grupo.pack(fill="x")
        _atualizar(raiz)
        for bloco in grupo.blocos:
            assert int(bloco.rotulo_legenda.cget("wraplength")) >= bloco._maior_palavra() - 1
        assert grupo.blocos[2].margem < c.NumeroResumo.MARGEM             # a margem encolheu para caber
    finally:
        frame.destroy()
        raiz.withdraw()


def test_numero_grande_encolhe_para_caber_inteiro(raiz):
    # "R$ -81" cortado no Crédito Estouro, na janela pequena
    frame = _na_largura(raiz, 290)
    try:
        grupo = c.GrupoNumeros(frame, [(147, "0256 do mês anterior"), (8, "itens a conferir", "atencao"),
                                       ("R$ -810,50", "diferença sem explicação", "erro")])
        grupo.pack(fill="x")
        _atualizar(raiz)
        pequeno, dinheiro = grupo.blocos[0], grupo.blocos[2]
        assert pequeno.fonte_numero.cget("size") == tema.TAMANHO_NUMERO_GRANDE          # "147" cabe: não muda
        assert dinheiro.fonte_numero.cget("size") < tema.TAMANHO_NUMERO_GRANDE
        assert dinheiro._largura_numero() <= dinheiro._largura - 2 * dinheiro.margem
        dinheiro.atualizar("1")                                                           # cabe de novo: volta
        _atualizar(raiz)
        assert dinheiro.fonte_numero.cget("size") == tema.TAMANHO_NUMERO_GRANDE
    finally:
        frame.destroy()
        raiz.withdraw()


def test_tabela_nunca_corta_um_valor(raiz):
    # ".838.244,51" no lugar de "5.838.244,51" na aba Hospital Exemplo de Honorários, na janela mínima
    frame = _na_largura(raiz, 300)
    try:
        tabela = c.TabelaSimples(frame, [c.Coluna("Total", peso=4), c.Coluna("PF (R$)", numero=True, peso=3),
                                         c.Coluna("PJ (R$)", numero=True, peso=3)],
                                 [("Contábil (2131 / 2132)", "83.748,35", "5.838.244,51"),
                                  ("PDFs de repasse", "9.210,00", "7.084,00")])
        tabela.pack(fill="x")
        _atualizar(raiz)
        valores = [r for r in tabela.winfo_children() if isinstance(r, ctk.CTkLabel)
                   and r.cget("text") in ("83.748,35", "5.838.244,51")]
        assert len(valores) == 2
        for rotulo in valores:
            assert rotulo.winfo_width() >= rotulo.cget("font").measure(rotulo.cget("text"))
            assert rotulo.winfo_x() + rotulo.winfo_width() <= tabela.winfo_width()    # inteiro dentro da tabela
        assert tabela.winfo_width() <= frame.winfo_width()
        texto = next(r for r in tabela.winfo_children() if isinstance(r, ctk.CTkLabel)
                     and r.cget("text") == "Contábil (2131 / 2132)")
        assert texto.winfo_reqwidth() <= tabela.grid_bbox(column=0, row=2)[2] + 1     # quebrou, não cortou
    finally:
        frame.destroy()
        raiz.withdraw()


def test_tabela_larga_continua_proporcional_ao_peso(raiz):
    frame = _na_largura(raiz, 700)
    try:
        tabela = c.TabelaSimples(frame, [c.Coluna("Total", peso=3), c.Coluna("Valor (R$)", numero=True, peso=2)],
                                 [("Balancete (conta 2132)", "366.298,38")])
        tabela.pack(fill="x")
        _atualizar(raiz)
        largura_texto, largura_valor = (tabela.grid_bbox(column=i, row=0)[2] for i in (0, 1))
        assert abs(largura_texto / largura_valor - 1.5) < 0.15
    finally:
        frame.destroy()
        raiz.withdraw()


def test_cartao_arquivo_estreito_poe_os_botoes_embaixo(raiz):
    # "Adicionar arquivos" na aba Hospital Exemplo de Honorários: os nomes quebravam no meio ("Balancet / e PF")
    frame = _na_largura(raiz, 300)
    try:
        cartao = c.CartaoArquivo(frame, "Relatórios do mês", tipo="arquivos", acumular=True)
        cartao.pack(fill="x")
        _atualizar(raiz)
        assert cartao.botoes_embaixo
        assert int(cartao._botoes.grid_info()["row"]) == 1
        # os nomes não encostam na borda direita (cobriam a linha e o canto arredondado do cartão)
        assert cartao._textos.winfo_x() + cartao._textos.winfo_width() <= cartao.winfo_width() - 8
        raiz.geometry("760x400")
        frame.configure(width=700)
        _atualizar(raiz)
        assert not cartao.botoes_embaixo and int(cartao._botoes.grid_info()["row"]) == 0
    finally:
        frame.destroy()
        raiz.withdraw()


def test_texto_quebravel_quebra_em_vez_de_cortar(raiz):
    frame = _na_largura(raiz, 200)
    try:
        rotulo = c.TextoQuebravel(frame, "Fundação Hospital Exemplo · set/2026",
                                  tema.fonte_texto_forte())
        rotulo.pack(fill="x")
        _atualizar(raiz)
        assert int(rotulo.rotulo.cget("wraplength")) <= 200
        assert rotulo.rotulo.winfo_reqwidth() <= frame.winfo_width() + 1
        largura = int(rotulo.rotulo.cget("wraplength"))
        _atualizar(raiz)
        assert int(rotulo.rotulo.cget("wraplength")) == largura          # estável: não continua encolhendo
    finally:
        frame.destroy()
        raiz.withdraw()


def test_linha_de_conferencia_quebra_em_vez_de_cortar(raiz):
    frame = _na_largura(raiz, 300)
    try:
        linha = c.LinhaConferencia(frame, "1 arquivo(s) não puderam ser lidos — veja os avisos e confira a pasta",
                                   "erro")
        linha.pack(fill="x")
        _atualizar(raiz)
        assert int(linha.rotulo_texto.cget("wraplength")) < 300
        assert linha.rotulo_texto.winfo_x() + linha.rotulo_texto.winfo_width() <= linha.winfo_width()
    finally:
        frame.destroy()
        raiz.withdraw()


def test_rodape_do_resultado_vai_para_duas_linhas_quando_nao_cabe(raiz):
    # Conferência ISS na janela mínima: o terceiro botão do rodapé saía cortado
    from central.modulo_base import InfoModulo
    from central.painel_base import PainelPadrao

    info = InfoModulo(chave="teste", nome="Teste", descricao="Teste.", contexto="Teste", icone="arquivo",
                      criar_painel=lambda pai: None)
    vistos = set()
    for largura_tela in (640, 1500):              # a coluna do resultado é metade: ~300 e ~730 px
        frame = _na_largura(raiz, largura_tela)
        try:
            painel = PainelPadrao(frame, info, com_cabecalho=False)
            painel.pack(fill="x")
            painel.resultado.mostrar_conteudo()
            botoes = painel.definir_botoes_resultado([("Abrir pasta", None, "pasta"), ("Ver avisos", None, "alerta"),
                                                      ("Novo", None, "mais")])
            _atualizar(raiz)
            rodape = painel.resultado.rodape
            largura = int(rodape.winfo_width() / ctk.ScalingTracker.get_widget_scaling(raiz))
            precisa = tema.LARGURA_MINIMA_PRINCIPAL_RODAPE + 2 * (tema.LARGURA_BOTAO_RODAPE + tema.ESPACO_PEQUENO)
            assert painel.rodape_em_duas_linhas == (largura < precisa)
            vistos.add(painel.rodape_em_duas_linhas)
            for botao in botoes.values():                               # nenhum botão sai do rodapé
                assert botao.winfo_x() + botao.winfo_width() <= rodape.winfo_width()
            assert list(botoes) == [b.cget("text") for b in rodape.winfo_children()]
        finally:
            frame.destroy()
            raiz.withdraw()
    assert vistos == {True, False}
