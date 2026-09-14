def parse_words(file_content):
    """Converte o conteudo de um TXT em uma lista de chaves."""
    if isinstance(file_content, bytes):
        try:
            file_content = file_content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise ValueError("O arquivo deve estar codificado em UTF-8.") from error

    words = []

    for line in file_content.splitlines():
        # A chave e preservada como aparece no arquivo. Somente linhas vazias
        # ou formadas exclusivamente por espacos sao ignoradas.
        if line.strip():
            words.append(line)

    if len(words) == 0:
        raise ValueError("O arquivo esta vazio.")

    if len(words) != len(set(words)):
        raise ValueError("O arquivo deve conter palavras unicas.")

    return words


def load_words(file_path):
    """Le e valida um arquivo de palavras armazenado no computador."""
    try:
        with open(file_path, "rb") as file:
            return parse_words(file.read())
    except (FileNotFoundError, OSError) as error:
        raise ValueError("Nao foi possivel ler o arquivo.") from error


def create_pages(words, page_size):
    """Cria paginas vazias e distribui os registros entre elas."""
    if not isinstance(page_size, int) or isinstance(page_size, bool):
        raise ValueError("O tamanho da pagina deve ser um numero inteiro.")

    if page_size <= 0:
        raise ValueError("O tamanho da pagina deve ser maior que zero.")

    if len(words) == 0:
        return []

    page_count = (len(words) + page_size - 1) // page_size
    pages = [[] for _ in range(page_count)]

    for record_index, word in enumerate(words):
        page_id = record_index // page_size
        pages[page_id].append(word)

    return pages


def table_scan(key, pages):
    """Percorre paginas e registros sequencialmente ate encontrar a chave."""
    page_reads = 0
    records_read = []

    for page_id, page in enumerate(pages):
        page_reads += 1

        for record_position, record in enumerate(page):
            records_read.append(record)

            if record == key:
                return {
                    "found": True,
                    "page_id": page_id,
                    "page_reads": page_reads,
                    "records_read": records_read,
                    "record_position": record_position,
                }

    return {
        "found": False,
        "page_id": None,
        "page_reads": page_reads,
        "records_read": records_read,
        "record_position": None,
    }
