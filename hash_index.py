# FR = capacidade de cada bucket principal
# NB = quantidade total de buckets
# NR = quantidade de registros


def calculate_bucket_count(nr, fr):
    """Calcula o menor inteiro NB que satisfaz NB > NR / FR."""
    if nr < 0:
        raise ValueError("A quantidade de registros nao pode ser negativa.")

    if fr <= 0:
        raise ValueError("A capacidade do bucket deve ser maior que zero.")

    return (nr // fr) + 1


def create_buckets(nb):
    """Cria NB buckets inicialmente vazios."""
    if nb <= 0:
        raise ValueError("A quantidade de buckets deve ser maior que zero.")

    buckets = []

    for _ in range(nb):
        buckets.append([])

    return buckets


def custom_hash(key, nb):
    """Mapeia uma chave para um endereco entre zero e NB - 1."""
    if nb <= 0:
        raise ValueError("A quantidade de buckets deve ser maior que zero.")

    hash_value = 0

    for char in key:
        hash_value = (hash_value * 31 + ord(char)) % nb

    return hash_value


def insert_entry(buckets, overflow_buckets, key, page_id, fr, nb):
    """Insere (chave, pagina) no bucket principal ou em seu overflow."""
    bucket_index = custom_hash(key, nb)
    entry = (key, page_id)

    if len(buckets[bucket_index]) < fr:
        buckets[bucket_index].append(entry)
        return False

    overflow_buckets[bucket_index].append(entry)
    return True


def build_index(pages, buckets, overflow_buckets, fr, nb):
    """Constroi o indice percorrendo pagina por pagina e registro por registro."""
    collision_count = 0

    for page_id, page in enumerate(pages):
        for key in page:
            sent_to_overflow = insert_entry(
                buckets,
                overflow_buckets,
                key,
                page_id,
                fr,
                nb,
            )

            if sent_to_overflow:
                collision_count += 1

    return collision_count


def calculate_index_statistics(buckets, overflow_buckets, nr):
    """Calcula as metricas pedidas para o indice construido."""
    if len(buckets) != len(overflow_buckets):
        raise ValueError("Buckets principais e de overflow devem corresponder.")

    primary_records = sum(len(bucket) for bucket in buckets)
    overflow_records = sum(len(bucket) for bucket in overflow_buckets)
    overflowed_bucket_count = sum(
        1 for bucket in overflow_buckets if len(bucket) > 0
    )
    total_indexed = primary_records + overflow_records

    if nr > 0:
        collision_rate = (overflow_records / nr) * 100
    else:
        collision_rate = 0

    if len(buckets) > 0:
        overflow_rate = (overflowed_bucket_count / len(buckets)) * 100
    else:
        overflow_rate = 0

    return {
        "primary_records": primary_records,
        "overflow_records": overflow_records,
        "total_indexed": total_indexed,
        # Segundo a RN14, somente entradas que excedem FR sao colisoes.
        "collision_count": overflow_records,
        "collision_rate": collision_rate,
        "overflowed_bucket_count": overflowed_bucket_count,
        "overflow_rate": overflow_rate,
    }


def search_index(key, pages, buckets, overflow_buckets, nb):
    """Busca no bucket calculado e confirma a chave na pagina de dados."""
    bucket_index = custom_hash(key, nb)
    page_id = None
    location = None
    bucket_position = None
    index_entries_read = 0

    for position, (entry_key, entry_page_id) in enumerate(buckets[bucket_index]):
        index_entries_read += 1

        if entry_key == key:
            page_id = entry_page_id
            location = "primary"
            bucket_position = position
            break

    if page_id is None:
        for position, (entry_key, entry_page_id) in enumerate(
            overflow_buckets[bucket_index]
        ):
            index_entries_read += 1

            if entry_key == key:
                page_id = entry_page_id
                location = "overflow"
                bucket_position = position
                break

    if page_id is None:
        return {
            "found": False,
            "page_id": None,
            "bucket_index": bucket_index,
            "page_reads": 0,
            "location": None,
            "bucket_position": None,
            "index_entries_read": index_entries_read,
            "record_position": None,
        }

    # O custo pedido considera paginas de dados. Os buckets estao em memoria.
    page_reads = 1

    for record_position, record in enumerate(pages[page_id]):
        if record == key:
            return {
                "found": True,
                "page_id": page_id,
                "bucket_index": bucket_index,
                "page_reads": page_reads,
                "location": location,
                "bucket_position": bucket_position,
                "index_entries_read": index_entries_read,
                "record_position": record_position,
            }

    # Este retorno so ocorreria se o indice e as paginas ficassem inconsistentes.
    return {
        "found": False,
        "page_id": page_id,
        "bucket_index": bucket_index,
        "page_reads": page_reads,
        "location": location,
        "bucket_position": bucket_position,
        "index_entries_read": index_entries_read,
        "record_position": None,
    }
