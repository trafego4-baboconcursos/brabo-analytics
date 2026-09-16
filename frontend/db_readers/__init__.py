"""
frontend/db_readers/ — Leitores do banco, um módulo por domínio.

Cada submódulo é dono das suas consultas e devolve as dataclasses de
``frontend/models.py``. Este ``__init__`` reexporta o que o resto do app
consome, para que ``from frontend.db_readers import read_meta`` continue
funcionando sem amarrar quem chama ao arquivo onde a função mora hoje.

Até setembro/2026 tudo isso vivia em ``frontend/database_reader.py``, que no
fim já era só uma lista de re-exports com três funções soltas. A migração
terminou: aquele arquivo não existe mais, e as funções que restavam foram para
``comparativo.py``, ``youtube_aulas.py`` e ``frontend/ad_accounts.py``.

Uma observação sobre imports: ``sales``, ``launches`` e ``typeform`` se
referenciam em ciclo (``sales`` → ``launches`` → ``typeform`` → ``sales``), por
isso essas três dependências entre si continuam sendo importadas dentro das
funções, não no topo do módulo. As demais são diretas.
"""
from frontend.db import _get_engine, _get_users_engine  # noqa: F401
from frontend.models import *  # noqa: F401, F403

from frontend.db_readers.ads_google import (  # noqa: F401
    _classify_google_type, read_daily_breakdown, read_google,
)
from frontend.db_readers.ads_meta import (  # noqa: F401
    find_ad_code_real_launches, get_historico_ad_codes, read_meta,
)
from frontend.db_readers.caminho_comprador import read_caminho_comprador  # noqa: F401
from frontend.db_readers.comparativo import read_comparativo  # noqa: F401
from frontend.db_readers.eventos import CORES_TIPO, eventos_por_dia, read_eventos  # noqa: F401
from frontend.db_readers.ga4 import (  # noqa: F401
    read_conversao_pagina_captura, read_landing_pages_por_etapa,
)
from frontend.db_readers.launches import (  # noqa: F401
    _ETL_SOURCES, autodetect_launch_data, count_campaigns_for_filter, create_launch,
    discover_launches, get_drive_thumbnails, get_etl_status, get_launch,
    get_platform_thumbnails, read_launch_config, save_launch_config,
)
from frontend.db_readers.leads import (  # noqa: F401
    read_ac_campaigns, read_ac_leads_for_attribution, read_ebook_compradores,
    read_lancamentos_anteriores, read_leads, read_leads_antigos_compradores,
    read_recorrencia_lancamento, read_term_campaign_map, read_utm_cobertura,
    read_vendas_por_dia_cadastro,
)
from frontend.db_readers.nomenclatura import (  # noqa: F401
    categorizar_campanha_google, categorizar_campanha_meta,
)
from frontend.db_readers.sales import (  # noqa: F401
    read_dia1_sales, read_forma_pagamento_entrada, read_hotmart_details,
    read_hotmart_recompra, read_qualidade_regiao, read_tmb_details, read_vendas,
    read_vendas_consolidado,
)
from frontend.db_readers.typeform import (  # noqa: F401
    _build_typeform_comparison, _generate_ia_insights, _get_typeform_fields,
    _get_typeform_forms, _reconstruct_tabular_df, _resolve_typeform_ids,
    read_perfil_por_anuncio, read_pesquisa_engajamento, read_typeform,
    read_typeform_count,
)
from frontend.db_readers.users import (  # noqa: F401
    PRODUCT_LABELS, ROLE_LABELS, _users_table_exists, bootstrap_admin_if_needed,
    create_invite, create_user, delete_invite, get_invite, get_user_by_email,
    get_user_by_id, list_invites, list_users, update_last_login, update_user,
    use_invite,
)
from frontend.db_readers.whatsapp_groups import (  # noqa: F401
    read_compradores_por_dia_grupo, read_leads_x_whatsapp, read_vendas_grupos_whatsapp,
    read_whatsapp_groups,
)
from frontend.db_readers.whatsapp_messages import (  # noqa: F401
    read_disparo_resumo, read_whatsapp_messages,
)
from frontend.db_readers.youtube_aulas import (  # noqa: F401
    read_aulas_ao_vivo, read_retencao_video, read_youtube_aulas,
)
