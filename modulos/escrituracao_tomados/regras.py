"""Regras de negócio: destino e códigos de cada nota (R1–R10, R13, R19). Sem arquivo e sem tela.

Ordem dos destinos quando a nota se encaixa em mais de um motivo (decisão do usuário,
28/09/2026): DUPLICADA -> situação (cancelada/substituída) -> NÃO INCLUÍDA (tomador/prestador)
-> JÁ ESCRITURADA -> LANÇAR À MÃO -> INCLUÍDA. "Já escriturada" vem antes de "lançar à mão"
para uma nota já digitada no site nunca voltar para a lista de digitação.

CFPS e código de retido só são calculados para as notas que serão escrituradas (INCLUÍDA e
LANÇAR À MÃO). Nas demais ficam em branco (decisão do usuário, 28/09/2026).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from modulos.escrituracao_tomados import configuracao as cfg
from modulos.escrituracao_tomados.conferencia import NotasEscrituradas, chave_nota
from modulos.escrituracao_tomados.gerador_txt import normalizar_texto, so_digitos
from modulos.escrituracao_tomados.modelos import (
    Aviso, Destino, GrupoArquivo, NotaTomada,
)

CENTAVO = Decimal("0.01")


def formatar_moeda(valor: Decimal) -> str:
    """Decimal('13943.28') -> '13.943,28'."""
    texto = f"{valor:,.2f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def e_da_fundacao(documento: str, outros_cnpjs=()) -> bool:
    """CNPJ com a raiz da Fundação ou um dos outros CNPJs da Fundação informados na tela, de
    outra raiz (ex.: um AME com CNPJ próprio — decisão do usuário, 01/10/2026). CPF nunca é."""
    digitos = so_digitos(documento)
    if len(digitos) != 14:
        return False
    return digitos.startswith(cfg.RAIZ_CNPJ_FUNDACAO) or \
        digitos in {so_digitos(c) for c in outros_cnpjs}


# ---------------------------------------------------------------------------
# Códigos (R5, R6)
# ---------------------------------------------------------------------------


def e_exportacao(nota: NotaTomada) -> bool:
    return nota.origem == "Exportação"


def codigo_cfps(nota: NotaTomada) -> str:
    """R5: pelo Local da Prestação que está na nota. Cidade Alfa -> 001; outro município -> 002.

    Exportações do site (sem local da prestação): o cfps que veio do site.
    """
    if e_exportacao(nota):
        return nota.cfps_site
    return "001" if normalizar_texto(nota.local_prestacao) == cfg.MUNICIPIO_SEDE else "002"


AVISO_INCIDENCIA_DIFERENTE = "Incidência diferente da cidade do prestador"

_CODIGOS_RETIDO = {  # (retido?, devido em Cidade Alfa?) -> código
    (False, True): "N", (False, False): "Z",
    (True, True): "S", (True, False): "X",
}


def codigo_retido(nota: NotaTomada) -> tuple[str | None, list[Aviso]]:
    """R6: código N/S/Z/X. Devolve (código ou None se não houver cidade para decidir, avisos).

    ISS devido em Cidade Alfa? Pelo município de incidência (PDF); sem ele, pela cidade do prestador.
    """
    avisos = []
    incidencia = normalizar_texto(nota.municipio_incidencia)
    cidade = normalizar_texto(nota.prestador_cidade)
    do_pdf = nota.origem == "PDF"
    if incidencia:
        base = incidencia
        if cidade and incidencia != cidade:
            avisos.append(_aviso(nota, AVISO_INCIDENCIA_DIFERENTE,
                                 f"Conferir: ISS devido em {incidencia}, prestador de {cidade}. "
                                 "O site escolhe as opções pela cidade do prestador."))
    else:
        base = cidade
        if do_pdf:
            avisos.append(_aviso(nota, "Incidência vazia",
                                 "A nota não informa o município de incidência do ISSQN: usada a "
                                 f"cidade do prestador ({cidade or 'não encontrada'})."))
    if not base:
        return None, avisos
    return _CODIGOS_RETIDO[(bool(nota.iss_retido), base == cfg.MUNICIPIO_SEDE)], avisos


def iss_calculado(nota: NotaTomada) -> Decimal:
    """(serviço - deduções) x alíquota, arredondado ao centavo (como o site calcula)."""
    return ((nota.valor_servico - nota.deducoes) * nota.aliquota / 100).quantize(
        CENTAVO, rounding=ROUND_HALF_UP)


def completar_iss_zerado(nota: NotaTomada) -> list[Aviso]:
    """R10 (decisão do usuário, 28/09/2026): nota com alíquota e "ISSQN Apurado" zerado (optante do
    Simples com ISS devido fora) vai com o ISS calculado — o site recusa imposto 0 quando há
    alíquota ("valor imposto (0.0) não coincide com o valor calculado")."""
    if not nota.iss_calculado:
        if nota.valor_iss != 0 or nota.aliquota <= 0 or nota.valor_servico <= nota.deducoes:
            return []
        nota.valor_iss = iss_calculado(nota)
        nota.iss_calculado = True
    return [_aviso(nota, "ISS da nota zerado: usado o calculado",
                   f"A nota traz alíquota de {formatar_moeda(nota.aliquota)}% e ISS zerado; no arquivo "
                   f"vai o ISS calculado, R$ {formatar_moeda(nota.valor_iss)} (o site exige "
                   "serviço x alíquota).")]


def completar_aliquota_vazia(nota: NotaTomada) -> list[Aviso]:
    """R10 (decisão do usuário, 29/09/2026): nota com "Alíquota Aplicada" em branco e ISS
    preenchido vai com a alíquota calculada, ISS ÷ (serviço - deduções), com 2 casas — o site
    recusa quando serviço x alíquota não dá o ISS informado (caso da nota 10418, 07/2026).
    Se nenhuma alíquota de 2 casas levar exatamente ao ISS da nota, a nota vai para lançar à mão.
    """
    if not nota.aliquota_calculada:
        base = nota.valor_servico - nota.deducoes
        if nota.aliquota != 0 or nota.valor_iss <= 0 or base <= 0:
            return []
        estimada = (nota.valor_iss / base * 100).quantize(CENTAVO, rounding=ROUND_HALF_UP)
        # a primeira (a estimada) e as vizinhas, caso o arredondamento da estimada não bata
        for candidata in (estimada, estimada - CENTAVO, estimada + CENTAVO):
            nota.aliquota = candidata
            if candidata > 0 and iss_calculado(nota) == nota.valor_iss:
                break
        else:
            nota.aliquota = Decimal("0.00")
            nota.destino = Destino.LANCAR_A_MAO
            motivo = (f"alíquota em branco na nota e nenhuma alíquota leva ao ISS de "
                      f"R$ {formatar_moeda(nota.valor_iss)}")
            nota.motivo = f"{nota.motivo}; {motivo}" if nota.motivo else motivo
            return []
        nota.aliquota_calculada = True
    return [_aviso(nota, "Alíquota em branco: calculada",
                   f"A nota traz ISS de R$ {formatar_moeda(nota.valor_iss)} sem alíquota; no arquivo "
                   f"vai a alíquota calculada, {formatar_moeda(nota.aliquota)}% (o site exige "
                   "serviço x alíquota = ISS).")]


def base_da_nota(nota: NotaTomada) -> Decimal:
    """Base de cálculo do ISS pela própria nota: a "BC ISSQN" (já sem desconto incondicionado e
    deduções); sem ela, serviço - deduções - desconto incondicionado (Usuário, 29/09/2026)."""
    if nota.base_calculo is not None:
        return nota.base_calculo
    return nota.valor_servico - nota.deducoes - nota.desconto_incondicionado


def conferir_iss(nota: NotaTomada) -> list[Aviso]:
    """R10: ISS informado x base de cálculo x alíquota. Só avisa; vale o ISS da nota.

    1. A nota é coerente? ISS x BC ISSQN x alíquota.
    2. Nota que vai no .txt: o site recalcula sobre serviço - deduções (V13/V15) — se a BC da nota
       for outra (ex.: benefício municipal), avisa que o site pode recusar a linha.
    """
    tolerancia = Decimal(cfg.TOLERANCIA_ISS)
    pela_base = (base_da_nota(nota) * nota.aliquota / 100).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    diferenca = abs(pela_base - nota.valor_iss)
    if diferenca > tolerancia:
        return [_aviso(nota, "ISS calculado diferente do informado",
                       f"ISS da nota R$ {formatar_moeda(nota.valor_iss)}; calculado sobre a base "
                       f"R$ {formatar_moeda(base_da_nota(nota))}: R$ {formatar_moeda(pela_base)} "
                       f"(diferença R$ {formatar_moeda(diferenca)}). Vale o ISS da nota.")]
    pelo_site = iss_calculado(nota)
    if nota.destino is Destino.INCLUIDA and abs(pelo_site - nota.valor_iss) > tolerancia:
        return [_aviso(nota, "Base de cálculo diferente de serviço - deduções",
                       f"A nota calcula o ISS sobre R$ {formatar_moeda(base_da_nota(nota))}, mas o "
                       f"site recalcula sobre serviço - deduções (R$ {formatar_moeda(pelo_site)} de "
                       "ISS) e pode recusar a linha. Confira antes de importar.")]
    return []


def _aviso(nota: NotaTomada, tipo: str, mensagem: str) -> Aviso:
    return Aviso(tipo=tipo, mensagem=mensagem, arquivo=nota.arquivo,
                 nota=f"{nota.numero} - {nota.prestador_nome}")


# ---------------------------------------------------------------------------
# Destino (R1, R2, R8, R9, R10)
# ---------------------------------------------------------------------------


def emitida_fora_da_competencia(nota: NotaTomada) -> bool:
    """Mês/ano da emissão diferente da competência (V17)."""
    return nota.competencia is not None and nota.data_emissao is not None and \
        (nota.data_emissao.year, nota.data_emissao.month) != (nota.competencia.ano, nota.competencia.mes)


def _destino(nota: NotaTomada, escrituradas: NotasEscrituradas | None,
             outros_cnpjs=()) -> tuple[Destino, str]:
    situacao = normalizar_texto(nota.situacao)
    if situacao not in cfg.SITUACOES_AUTORIZADAS:
        if situacao == cfg.SITUACAO_CANCELADA:
            return Destino.NAO_INCLUIDA, "nota cancelada"
        if situacao.startswith(cfg.SITUACAO_SUBSTITUIDA):
            return Destino.NAO_INCLUIDA, "nota substituída"
        return Destino.NAO_INCLUIDA, f"situação não prevista: {nota.situacao}"

    # prestador antes do tomador: numa nota de serviço PRESTADO o tomador também não é a
    # Fundação (é o cliente dela), e o motivo que explica é o do prestador
    if e_da_fundacao(nota.prestador_documento, outros_cnpjs):
        return Destino.NAO_INCLUIDA, "prestador é a própria Fundação (nota de serviço prestado)"
    if not nota.tomador_documento:
        # decisão do usuário (28/09/2026): o programa não decide sozinho que a Fundação é tomadora
        motivo = "tomador não identificado na nota"
        if e_da_fundacao(nota.intermediario_documento, outros_cnpjs):
            motivo += "; a Fundação aparece como intermediária"
        return Destino.NAO_INCLUIDA, motivo
    if not e_da_fundacao(nota.tomador_documento, outros_cnpjs):
        return Destino.NAO_INCLUIDA, (f"tomador não é estabelecimento da Fundação "
                                      f"({nota.tomador_documento})")
    if nota.valor_servico <= 0:
        # decisão do usuário (28/09/2026), notas 8592262 e 8592280: não há valor nem ISS a declarar
        return Destino.NAO_INCLUIDA, "nota sem valor de serviço (R$ 0,00)"

    if escrituradas is not None:
        arquivo = escrituradas.arquivo_da_nota(nota.numero, nota.prestador_documento)
        if arquivo:
            return Destino.JA_ESCRITURADA, f"já escriturada ({arquivo})"
        curta = escrituradas.digitada_com_numero_curto(nota.numero, nota.prestador_documento,
                                                       nota.valor_servico)
        if curta:
            return Destino.JA_ESCRITURADA, f"já escriturada ({curta[0]}, digitada como {curta[1]})"

    # número com mais de 8 dígitos não é mais motivo para lançar à mão: entra com os 8 últimos
    # dígitos (R8, ajustar_numeros_longos)
    motivos = []
    if e_exportacao(nota) and nota.iss_retido is None:
        motivos.append(f"imposto retido \"{nota.retido_site}\" no site (não é SIM/NÃO)")
    if nota.motivo_leitura:
        motivos.append(nota.motivo_leitura)           # NFS-e de São Paulo (R18)
    elif not e_exportacao(nota) and \
            normalizar_texto(nota.tipo_tributacao) != cfg.TRIBUTACAO_TRIBUTAVEL:
        motivos.append(f"tipo de tributação \"{nota.tipo_tributacao}\" (não é Operação "
                       "Tributável)")
    if nota.desconto_incondicionado > 0:
        motivos.append(f"desconto incondicionado de R$ "
                       f"{formatar_moeda(nota.desconto_incondicionado)} (o arquivo não tem "
                       "esse campo)")
    if emitida_fora_da_competencia(nota):
        # decisão do usuário (07/10/2026, V17): o site recusa a nota cuja emissão não está no mês
        # de referência do arquivo ("data emissao ... não esta dentro da referencia")
        motivos.append(f"emitida em {nota.data_emissao:%m/%Y}, competência "
                       f"{nota.competencia.texto} (o site só aceita no arquivo a nota emitida no "
                       "mês da competência)")
    if motivos:
        return Destino.LANCAR_A_MAO, "; ".join(motivos)
    return Destino.INCLUIDA, ""


def classificar(notas: list[NotaTomada],
                escrituradas: NotasEscrituradas | None = None,
                outros_cnpjs=()) -> list[Aviso]:
    """Preenche destino, motivo, CFPS e código de retido de cada nota. Devolve os avisos.

    Notas já marcadas como DUPLICADA (na leitura) ficam como estão. `outros_cnpjs`: CNPJs da
    Fundação de outra raiz (R1), informados na tela.
    """
    avisos: list[Aviso] = []
    for nota in notas:
        if nota.destino is Destino.DUPLICADA:
            continue
        nota.cfps = nota.codigo_retido = nota.numero_arquivo = ""
        nota.destino, nota.motivo = _destino(nota, escrituradas, outros_cnpjs)
        if nota.destino not in (Destino.INCLUIDA, Destino.LANCAR_A_MAO):
            continue
        avisos += completar_aliquota_vazia(nota)
        avisos += completar_iss_zerado(nota)
        avisos += conferir_iss(nota)
        nota.cfps = codigo_cfps(nota)
        if nota.iss_retido is None:
            continue                  # retido não informado (exportação com M, NFS-e de SP): a
                                      # pessoa decide ao digitar
        codigo, avisos_retido = codigo_retido(nota)
        avisos += avisos_retido
        if codigo is None:
            motivo = "cidade do prestador não encontrada (não dá para saber onde o ISS é devido)"
            nota.destino = Destino.LANCAR_A_MAO
            nota.motivo = f"{nota.motivo}; {motivo}" if nota.motivo else motivo
        else:
            nota.codigo_retido = codigo
        if not nota.iss_retido and any(a.tipo == AVISO_INCIDENCIA_DIFERENTE for a in avisos_retido):
            # decisão do usuário (02/10/2026, V16): o site escolhe as opções pela cidade do prestador
            # e recusou a nota 144 (prestador de fora, ISS em Cidade Alfa, "Não Retido"):
            # "A retenção informada N não é válida. Esperado o valor S". A retida (nota 3115, S)
            # foi aceita e continua no arquivo.
            motivo = (f"ISS devido em {normalizar_texto(nota.municipio_incidencia)}, prestador de "
                      f"{normalizar_texto(nota.prestador_cidade)}, não retido (o site recusa o "
                      "imposto retido da nota)")
            nota.destino = Destino.LANCAR_A_MAO
            nota.motivo = f"{nota.motivo}; {motivo}" if nota.motivo else motivo
    ajustar_numeros_longos(notas, escrituradas)
    return avisos


# ---------------------------------------------------------------------------
# Não Optante sem imposto federal retido (R19) — pedido da chefia, 16/10/2026
# ---------------------------------------------------------------------------


DESTINOS_TOMADOS = (Destino.INCLUIDA, Destino.LANCAR_A_MAO, Destino.JA_ESCRITURADA)


def marcar_falar_com_fornecedor(notas: list[NotaTomada]) -> list[Aviso]:
    """Marca as notas de prestador "Não Optante" sem nenhum imposto federal retido (IRRF,
    Contribuição Previdenciária e Contribuições Sociais em branco). O ISS não entra na regra.
    Só PDF (a exportação do site não traz os federais) e só nota que a Fundação tomou: INCLUÍDA,
    LANÇAR À MÃO ou JÁ ESCRITURADA. Ficam de fora as duplicadas e as não incluídas (cancelada,
    substituída, serviço prestado pela própria Fundação, tomador de fora, valor zero). Não muda
    o destino nem o .txt. Federal que não pôde ser lido: aviso."""
    avisos: list[Aviso] = []
    for nota in notas:
        nota.falar_com_fornecedor = False
        if nota.origem != "PDF" or nota.regime != "N" or nota.destino not in DESTINOS_TOMADOS:
            continue
        if not nota.federais_lidos:
            avisos.append(_aviso(nota, "Impostos federais não lidos",
                                 "Prestador Não Optante: o quadro de tributação federal da nota "
                                 "não pôde ser lido; conferir no PDF se houve retenção."))
            continue
        nota.falar_com_fornecedor = nota.total_federais_retidos == 0
    return avisos


# ---------------------------------------------------------------------------
# Número com mais de 8 dígitos (R8) — decisão da chefia, 28/09/2026
# ---------------------------------------------------------------------------


def numero_longo(numero: str) -> bool:
    return len(so_digitos(numero).lstrip("0")) > 8


def oito_ultimos_digitos(numero: str) -> str:
    """2026000000090 -> '00000090' (o número que vai no .txt)."""
    return so_digitos(numero)[-8:]


def ajustar_numeros_longos(notas: list[NotaTomada], escrituradas: NotasEscrituradas | None) -> None:
    """Nota INCLUÍDA com número de mais de 8 dígitos entra no .txt com os 8 últimos dígitos, e o
    número é corrigido no site depois de importar (aba "Corrigir número no site").

    Proteções (o site recusa o arquivo INTEIRO se um número se repetir, V3):
    - o número ajustado já existe no site para o prestador (com outro valor; com o mesmo valor a
      nota já seria "já escriturada") -> lançar à mão;
    - outra nota do mesmo prestador fica com o mesmo número no mesmo arquivo -> lançar à mão.
    """
    ocupados: set[tuple] = set()       # (tomador, competência, número no arquivo, prestador)

    def chave(nota, numero):
        return (so_digitos(nota.tomador_documento), nota.competencia,
                so_digitos(numero).lstrip("0") or "0", so_digitos(nota.prestador_documento))

    for nota in notas:
        if nota.destino is Destino.INCLUIDA and not numero_longo(nota.numero):
            ocupados.add(chave(nota, nota.numero))
    for nota in notas:
        if nota.destino is not Destino.INCLUIDA or not numero_longo(nota.numero):
            continue
        ajustado = oito_ultimos_digitos(nota.numero)
        curto = ajustado.lstrip("0") or "0"
        no_site = escrituradas.arquivo_da_nota(curto, nota.prestador_documento) if escrituradas else None
        if no_site:
            nota.destino = Destino.LANCAR_A_MAO
            nota.motivo = (f"número com mais de 8 dígitos: o número ajustado ({curto}) já existe no "
                           f"site para este prestador ({no_site}), com outro valor")
        elif chave(nota, ajustado) in ocupados:
            nota.destino = Destino.LANCAR_A_MAO
            nota.motivo = (f"número com mais de 8 dígitos: o número ajustado ({curto}) repetiria "
                           "outra nota deste prestador no mesmo arquivo")
        else:
            ocupados.add(chave(nota, ajustado))
            nota.numero_arquivo = ajustado
            nota.motivo = f"número ajustado para {ajustado}: corrigir no site para {nota.numero}"


# ---------------------------------------------------------------------------
# Duplicidades entre PDFs e exportações (R13)
# ---------------------------------------------------------------------------


def _divergencias(pdf: NotaTomada, exportada: NotaTomada) -> list[str]:
    diferencas = []
    for rotulo, valor_pdf, valor_site in (
            ("valor do serviço", pdf.valor_servico, exportada.valor_servico),
            ("ISS", pdf.valor_iss, exportada.valor_iss),
            ("alíquota", pdf.aliquota, exportada.aliquota)):
        if valor_pdf != valor_site:
            diferencas.append(f"{rotulo}: PDF {formatar_moeda(valor_pdf)}, "
                              f"exportação {formatar_moeda(valor_site)}")
    if codigo_cfps(pdf) != exportada.cfps_site:
        diferencas.append(f"CFPS: PDF {codigo_cfps(pdf)}, exportação {exportada.cfps_site}")
    if pdf.regime != exportada.regime:
        diferencas.append(f"regime: PDF {pdf.regime}, exportação {exportada.regime}")
    if exportada.iss_retido is None or bool(pdf.iss_retido) != exportada.iss_retido:
        texto_pdf = "SIM" if pdf.iss_retido else "NÃO"
        diferencas.append(f"imposto retido: PDF {texto_pdf}, exportação {exportada.retido_site}")
    return diferencas


def resolver_duplicidades(notas: list[NotaTomada]) -> list[Aviso]:
    """R13, antes de classificar. A mesma nota (número + prestador) em mais de um lugar entra uma
    vez: PDF e exportação -> vale o PDF (diferenças viram aviso); duas exportações -> vale a
    primeira. As outras ficam DUPLICADA. (PDF repetido na pasta já é tratado na leitura.)
    """
    avisos: list[Aviso] = []
    pdfs: dict = {}
    for nota in notas:
        if not e_exportacao(nota) and nota.destino is not Destino.DUPLICADA:
            pdfs.setdefault(chave_nota(nota.numero, nota.prestador_documento), nota)
    exportadas: dict = {}
    for nota in notas:
        if not e_exportacao(nota) or nota.destino is Destino.DUPLICADA:
            continue
        chave = chave_nota(nota.numero, nota.prestador_documento)
        pdf = pdfs.get(chave)
        if pdf is not None:
            nota.destino = Destino.DUPLICADA
            nota.motivo = f"a mesma nota veio em PDF ({pdf.arquivo}); vale o PDF"
            for diferenca in _divergencias(pdf, nota):
                avisos.append(_aviso(nota, "Divergência PDF x exportação", diferenca))
            continue
        primeira = exportadas.setdefault(chave, nota)
        if primeira is not nota:
            nota.destino = Destino.DUPLICADA
            nota.motivo = f"a mesma nota está em outra exportação ({primeira.arquivo})"
    return avisos


# ---------------------------------------------------------------------------
# Agrupamento (R4)
# ---------------------------------------------------------------------------


def agrupar_para_arquivos(notas: list[NotaTomada]) -> list[GrupoArquivo]:
    """Um grupo (= um .txt) por CNPJ do tomador + competência, só com as notas INCLUÍDAS."""
    grupos: dict[tuple, GrupoArquivo] = {}
    for nota in notas:
        if nota.destino is not Destino.INCLUIDA:
            continue
        tomador = so_digitos(nota.tomador_documento)
        grupo = grupos.get((tomador, nota.competencia))
        if grupo is None:
            grupo = grupos[(tomador, nota.competencia)] = GrupoArquivo(
                tomador, nota.tomador_nome, nota.competencia)
        grupo.notas.append(nota)
    return [grupos[chave] for chave in sorted(grupos)]
