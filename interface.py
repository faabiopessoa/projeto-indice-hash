from time import perf_counter

import pandas as pd
import streamlit as st

from data import create_pages, parse_words, table_scan
from hash_index import (
    build_index,
    calculate_bucket_count,
    calculate_index_statistics,
    create_buckets,
    search_index,
)
from visualization import (
    format_decimal,
    format_number,
    format_time,
    load_styles,
    render_bucket_neighborhood,
    render_bucket_contents,
    render_hash_flow,
    render_header,
    render_page_contents,
    render_page_preview,
    render_section_intro,
    show_dataframe,
    show_metrics,
)


FR = 10


def initialize_state():
    defaults = {
        "index_ready": False,
        "file_name": None,
        "words": [],
        "pages": [],
        "page_size": None,
        "nr": 0,
        "nb": 0,
        "buckets": [],
        "overflow_buckets": [],
        "statistics": {},
        "build_time": 0.0,
        "search_result": None,
        "scan_result": None,
        "last_search_key": "",
        "scan_page_selector": 0,
        "explorer_bucket": 0,
        "explorer_page": 0,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def index_is_ready():
    return st.session_state.index_ready


def construct_index(uploaded_file, page_size):
    words = parse_words(uploaded_file.getvalue())
    pages = create_pages(words, page_size)
    nr = len(words)
    nb = calculate_bucket_count(nr, FR)
    buckets = create_buckets(nb)
    overflow_buckets = create_buckets(nb)

    build_start = perf_counter()
    collision_count = build_index(
        pages, buckets, overflow_buckets, FR, nb
    )
    build_time = perf_counter() - build_start
    statistics = calculate_index_statistics(buckets, overflow_buckets, nr)

    if collision_count != statistics["collision_count"]:
        raise RuntimeError("A contagem de colisoes ficou inconsistente.")
    if statistics["total_indexed"] != nr:
        raise RuntimeError("Nem todos os registros foram inseridos no indice.")

    st.session_state.update(
        index_ready=True,
        file_name=uploaded_file.name,
        words=words,
        pages=pages,
        page_size=page_size,
        nr=nr,
        nb=nb,
        buckets=buckets,
        overflow_buckets=overflow_buckets,
        statistics=statistics,
        build_time=build_time,
        search_result=None,
        scan_result=None,
        last_search_key="",
        scan_page_selector=0,
        explorer_bucket=0,
        explorer_page=0,
    )


def render_sidebar():
    with st.sidebar:
        st.header("Preparação dos dados")
        st.caption(
            "Selecione o TXT e defina quantos registros cabem em cada página."
        )

        with st.form("build_index_form", clear_on_submit=False):
            uploaded_file = st.file_uploader(
                "Arquivo de palavras",
                type=["txt"],
                help="O arquivo deve estar em UTF-8 e conter uma chave única por linha.",
            )
            page_size = st.number_input(
                "Registros por página",
                min_value=1,
                value=100,
                step=1,
                format="%d",
            )
            submitted = st.form_submit_button(
                "Carregar e construir índice",
                type="primary",
                width="stretch",
            )

        if submitted:
            if uploaded_file is None:
                st.error("Selecione um arquivo TXT antes de continuar.")
            else:
                try:
                    with st.spinner("Criando páginas e construindo o índice..."):
                        construct_index(uploaded_file, int(page_size))
                    st.success("Índice criado com sucesso.")
                except ValueError as error:
                    st.error(str(error))

        if index_is_ready():
            st.divider()
            st.markdown("##### Índice atual")
            st.write(f"**Arquivo:** {st.session_state.file_name}")
            st.write(f"**Tamanho da página:** {format_number(st.session_state.page_size)}")
            st.write(f"**FR:** {FR} registros")

        st.divider()
        st.markdown("##### Convenções visuais")
        st.markdown(":blue[**Azul:** caminho da busca HASH]")
        st.markdown(":orange[**Laranja:** overflow]")
        st.markdown(":green[**Verde:** registro encontrado]")
        st.markdown(":red[**Vermelho:** registro não encontrado]")
        st.caption("As buscas são case-sensitive: Apple ≠ apple.")


def render_empty_state(section_name):
    st.info(f"Construa o índice na barra lateral para acessar {section_name}.")


def render_overview_tab():
    st.subheader("Dados e construção do índice")
    render_section_intro(
        "Da carga do TXT até a distribuição das entradas nos buckets."
    )

    if not index_is_ready():
        render_empty_state("o resumo dos dados")
        st.markdown("#### Fluxo desta etapa")
        st.markdown(
            "`TXT` → `páginas vazias` → `registros nas páginas` → "
            "`NB buckets` → `índice construído`"
        )
        return

    stats = st.session_state.statistics
    nr = st.session_state.nr
    nb = st.session_state.nb
    show_metrics(
        [
            ("NR · Registros", format_number(nr)),
            ("Páginas criadas", format_number(len(st.session_state.pages))),
            ("Tamanho da página", format_number(st.session_state.page_size)),
            ("FR · Capacidade", FR),
            ("NB · Buckets", format_number(nb)),
        ]
    )

    quotient = nr / FR
    quotient_text = (
        format_number(int(quotient))
        if quotient.is_integer()
        else format_decimal(quotient)
    )
    st.markdown(
        f"""
        <div class="formula-box">
            <strong>Dimensionamento:</strong> NB &gt; NR / FR &nbsp;→&nbsp;
            {format_number(nb)} &gt; {quotient_text} &nbsp;✓
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Colisões e overflow")
    show_metrics(
        [
            ("Colisões", format_number(stats["collision_count"])),
            ("Taxa de colisões", f"{format_decimal(stats['collision_rate'])}%"),
            (
                "Buckets em overflow",
                format_number(stats["overflowed_bucket_count"]),
            ),
            ("Taxa de overflow", f"{format_decimal(stats['overflow_rate'])}%"),
            (
                "Tempo de construção",
                f"{format_decimal(st.session_state.build_time, 4)} s",
            ),
        ]
    )

    distribution_column, formula_column = st.columns(2)
    total = stats["total_indexed"]
    primary_percentage = stats["primary_records"] / total
    overflow_percentage = stats["overflow_records"] / total

    with distribution_column:
        st.markdown("#### Distribuição das entradas")
        st.write(
            f"**Bucket principal:** {format_number(stats['primary_records'])} "
            f"({format_decimal(primary_percentage * 100)}%)"
        )
        st.progress(primary_percentage)
        st.write(
            f"**Overflow:** {format_number(stats['overflow_records'])} "
            f"({format_decimal(overflow_percentage * 100)}%)"
        )
        st.progress(overflow_percentage)
        st.success(
            f"Integridade verificada: {format_number(total)} de "
            f"{format_number(nr)} registros indexados."
        )

    with formula_column:
        st.markdown("#### Como as taxas são calculadas")
        st.code(
            "taxa de colisões = entradas no overflow / NR\n"
            "taxa de overflow = buckets com overflow / NB",
            language=None,
        )
        st.caption(
            "Conforme a RN14, uma colisão só é contabilizada quando o "
            "bucket principal já atingiu FR e a entrada vai para o overflow."
        )

    st.markdown("### Primeira e última página")
    first_column, last_column = st.columns(2)
    with first_column:
        render_page_preview(st.session_state.pages, 0)
    with last_column:
        render_page_preview(
            st.session_state.pages, len(st.session_state.pages) - 1
        )

    with st.expander("Ver distribuição da quantidade de registros por bucket"):
        occupancy_count = {}
        for primary, overflow in zip(
            st.session_state.buckets, st.session_state.overflow_buckets
        ):
            occupancy = len(primary) + len(overflow)
            occupancy_count[occupancy] = occupancy_count.get(occupancy, 0) + 1

        occupancies = sorted(occupancy_count)
        chart_data = pd.DataFrame(
            {
                "Registros por bucket": occupancies,
                "Quantidade de buckets": [
                    occupancy_count[value] for value in occupancies
                ],
            }
        ).set_index("Registros por bucket")
        st.bar_chart(chart_data)
        st.caption(
            "FR = 10 limita o bucket principal; valores maiores que 10 "
            "representam buckets com overflow."
        )


def execute_hash_search(key):
    start = perf_counter()
    result = search_index(
        key,
        st.session_state.pages,
        st.session_state.buckets,
        st.session_state.overflow_buckets,
        st.session_state.nb,
    )
    result.update(elapsed_ms=(perf_counter() - start) * 1000, key=key)
    st.session_state.update(
        search_result=result,
        scan_result=None,
        last_search_key=key,
        scan_page_selector=0,
        explorer_bucket=result["bucket_index"],
    )
    if result["page_id"] is not None:
        st.session_state.explorer_page = result["page_id"]


def render_search_tab():
    st.subheader("Busca pelo índice HASH")
    render_section_intro(
        "A busca consulta somente o bucket calculado e, se necessário, seu overflow."
    )

    if not index_is_ready():
        render_empty_state("a busca pelo índice")
        return

    with st.form("hash_search_form", border=False):
        input_column, button_column = st.columns([5, 1], vertical_alignment="bottom")
        with input_column:
            search_key = st.text_input(
                "Chave de busca",
                value=st.session_state.last_search_key,
                placeholder="Ex.: Apple ou water",
                help="Maiúsculas e minúsculas são diferentes. A chave não é normalizada.",
            )
        with button_column:
            submitted = st.form_submit_button(
                "Buscar pelo índice", type="primary", width="stretch"
            )

    if submitted:
        if search_key == "":
            st.error("Digite uma chave para realizar a busca.")
        else:
            execute_hash_search(search_key)

    result = st.session_state.search_result
    if result is None:
        st.info("Digite uma chave para visualizar o caminho percorrido pelo índice.")
        return

    st.markdown("### Caminho da busca")
    render_hash_flow(result, st.session_state.nb)
    render_bucket_neighborhood(
        result["bucket_index"],
        st.session_state.buckets,
        st.session_state.overflow_buckets,
        FR,
    )
    show_metrics(
        [
            ("Bucket calculado", format_number(result["bucket_index"])),
            (
                "Entradas do índice examinadas",
                format_number(result["index_entries_read"]),
            ),
            ("Páginas de dados lidas", format_number(result["page_reads"])),
            ("Tempo da busca", format_time(result["elapsed_ms"])),
        ]
    )

    if result["found"]:
        st.success(
            f"A chave '{result['key']}' foi encontrada na página "
            f"{format_number(result['page_id'])}."
        )
    else:
        st.error(
            f"A chave '{result['key']}' não existe no índice. "
            "Nenhuma página de dados foi acessada."
        )

    bucket_column, page_column = st.columns([1, 1.15])
    with bucket_column:
        render_bucket_contents(
            result["bucket_index"],
            st.session_state.buckets,
            st.session_state.overflow_buckets,
            FR,
            result["key"],
            result["location"],
            result["bucket_position"],
        )
    with page_column:
        if result["page_id"] is None:
            st.markdown("#### Página de dados")
            st.info(
                "Nenhuma página foi acessada porque a chave não foi "
                "localizada no bucket calculado."
            )
        else:
            render_page_contents(
                result["page_id"],
                st.session_state.pages,
                result["key"],
                result["record_position"],
            )

    with st.expander("Ver a função HASH utilizada"):
        st.code(
            "def custom_hash(key, nb):\n"
            "    hash_value = 0\n\n"
            "    for char in key:\n"
            "        hash_value = (hash_value * 31 + ord(char)) % nb\n\n"
            "    return hash_value",
            language="python",
        )
        st.caption(
            "A função é própria, determinística e não utiliza hash() do Python."
        )


def execute_table_scan():
    key = st.session_state.search_result["key"]
    start = perf_counter()
    result = table_scan(key, st.session_state.pages)
    result.update(elapsed_ms=(perf_counter() - start) * 1000, key=key)
    st.session_state.scan_result = result
    st.session_state.scan_page_selector = (
        len(st.session_state.pages) - 1
        if result["page_id"] is None
        else result["page_id"]
    )


def render_scan_records(scan_result):
    st.markdown("### Registros percorridos")
    st.caption(
        "Todos os registros lidos estão disponíveis por página, sem "
        "renderizar centenas de milhares de elementos simultaneamente."
    )
    last_read_page = scan_result["page_reads"] - 1
    selected_page = int(
        st.number_input(
            "Página do percurso",
            min_value=0,
            max_value=last_read_page,
            step=1,
            format="%d",
            key="scan_page_selector",
        )
    )
    page = st.session_state.pages[selected_page]
    records_before = sum(
        len(previous) for previous in st.session_state.pages[:selected_page]
    )
    read_on_page = max(
        0,
        min(len(page), len(scan_result["records_read"]) - records_before),
    )
    rows = [
        {
            "Ordem da leitura": records_before + position + 1,
            "Posição na página": position,
            "Registro": record,
        }
        for position, record in enumerate(page[:read_on_page])
    ]
    st.write(
        f"**Página {format_number(selected_page)}:** "
        f"{format_number(read_on_page)} registros examinados"
    )

    if selected_page == last_read_page:
        st.markdown("**Últimos registros examinados nesta página**")
        show_dataframe(
            pd.DataFrame(rows[-8:]),
            height=350,
            highlighted_key=scan_result["key"],
            key_column="Registro",
        )
        with st.expander("Ver todos os registros examinados nesta página"):
            show_dataframe(
                pd.DataFrame(rows),
                height=480,
                highlighted_key=scan_result["key"],
                key_column="Registro",
            )
    else:
        show_dataframe(pd.DataFrame(rows), height=480)

    if selected_page == last_read_page and scan_result["found"]:
        st.success(
            f"A varredura parou ao encontrar a chave na posição "
            f"{format_number(scan_result['record_position'])}."
        )
    elif selected_page == last_read_page:
        st.error("A varredura chegou ao fim da tabela sem encontrar a chave.")


def render_scan_tab():
    st.subheader("Table Scan e comparação")
    render_section_intro(
        "A varredura ignora o índice e percorre as páginas em ordem."
    )

    if not index_is_ready():
        render_empty_state("o Table Scan")
        return

    index_result = st.session_state.search_result
    if index_result is None:
        st.info(
            "Primeiro execute uma busca na aba 'Busca HASH'. A mesma chave "
            "será usada para comparar os dois métodos."
        )
        return

    st.write(f"Chave selecionada: **{index_result['key']}**")
    if st.button("Executar Table Scan", type="primary"):
        execute_table_scan()

    scan_result = st.session_state.scan_result
    if scan_result is None:
        st.info("Clique no botão para iniciar a leitura sequencial.")
        return

    if scan_result["found"]:
        st.success(
            f"A chave foi encontrada na página {format_number(scan_result['page_id'])}."
        )
    else:
        st.error("A chave não foi encontrada após percorrer toda a tabela.")

    index_column, scan_column = st.columns(2)
    with index_column:
        with st.container(border=True):
            st.markdown("### Índice HASH")
            show_metrics(
                [
                    ("Páginas de dados", format_number(index_result["page_reads"])),
                    ("Tempo", format_time(index_result["elapsed_ms"])),
                ]
            )
            st.caption(
                "O bucket está em memória e não entra no custo de páginas de dados."
            )
    with scan_column:
        with st.container(border=True):
            st.markdown("### Table Scan")
            show_metrics(
                [
                    ("Páginas lidas", format_number(scan_result["page_reads"])),
                    ("Tempo", format_time(scan_result["elapsed_ms"])),
                ]
            )
            st.caption(
                f"Registros examinados: "
                f"{format_number(len(scan_result['records_read']))}"
            )

    page_difference = scan_result["page_reads"] - index_result["page_reads"]
    page_reduction = (
        page_difference / scan_result["page_reads"] * 100
        if scan_result["page_reads"] > 0
        else 0
    )
    time_difference = scan_result["elapsed_ms"] - index_result["elapsed_ms"]
    time_reduction = (
        time_difference / scan_result["elapsed_ms"] * 100
        if scan_result["elapsed_ms"] > 0
        else 0
    )
    show_metrics(
        [
            ("Páginas evitadas", format_number(page_difference)),
            ("Redução no custo", f"{format_decimal(page_reduction)}%"),
            ("Diferença de tempo", format_time(time_difference)),
            ("Redução no tempo", f"{format_decimal(time_reduction)}%"),
        ]
    )

    st.markdown("### Comparação das páginas de dados lidas")
    st.bar_chart(
        pd.DataFrame(
            {
                "Método": ["Índice HASH", "Table Scan"],
                "Páginas de dados": [
                    index_result["page_reads"],
                    scan_result["page_reads"],
                ],
            }
        ).set_index("Método")
    )
    st.caption(
        "Os tempos são medidos com perf_counter() e podem variar. "
        "As páginas lidas são determinísticas para a mesma chave."
    )
    render_scan_records(scan_result)


def render_explorer_tab():
    st.subheader("Explorador de estruturas")
    render_section_intro(
        "Inspecione qualquer bucket ou página criada pelo programa."
    )

    if not index_is_ready():
        render_empty_state("o explorador")
        return

    bucket_column, page_column = st.columns(2)
    search_result = st.session_state.search_result

    with bucket_column:
        bucket_id = int(
            st.number_input(
                "ID do bucket",
                min_value=0,
                max_value=st.session_state.nb - 1,
                step=1,
                format="%d",
                key="explorer_bucket",
            )
        )
        is_searched_bucket = (
            search_result is not None
            and search_result["bucket_index"] == bucket_id
        )
        render_bucket_contents(
            bucket_id,
            st.session_state.buckets,
            st.session_state.overflow_buckets,
            FR,
            search_result["key"] if is_searched_bucket else None,
            search_result["location"] if is_searched_bucket else None,
            search_result["bucket_position"] if is_searched_bucket else None,
        )

    with page_column:
        page_id = int(
            st.number_input(
                "ID da página",
                min_value=0,
                max_value=len(st.session_state.pages) - 1,
                step=1,
                format="%d",
                key="explorer_page",
            )
        )
        is_searched_page = (
            search_result is not None
            and search_result["page_id"] == page_id
        )
        render_page_contents(
            page_id,
            st.session_state.pages,
            search_result["key"] if is_searched_page else None,
            search_result["record_position"] if is_searched_page else None,
        )


def create_app():
    st.set_page_config(
        page_title="Índice HASH Estático",
        page_icon="🔎",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    load_styles()
    initialize_state()
    render_sidebar()
    render_header(index_is_ready(), st.session_state.file_name)

    tabs = st.tabs(
        [
            "1 · Dados e índice",
            "2 · Busca HASH",
            "3 · Table Scan",
            "4 · Explorar estruturas",
        ],
        key="main_navigation",
        on_change="rerun",
    )
    render_functions = [
        render_overview_tab,
        render_search_tab,
        render_scan_tab,
        render_explorer_tab,
    ]

    for tab, render_function in zip(tabs, render_functions):
        with tab:
            render_function()
