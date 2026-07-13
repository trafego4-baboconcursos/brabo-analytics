# Re-exporta tudo de database_reader para compatibilidade e nova estrutura de namespace.
# O código pode ser movido para os módulos de domínio abaixo incrementalmente,
# uma vez que os testes em tests/ estejam cobrindo as funções migradas.
from frontend.database_reader import *  # noqa: F401, F403
from frontend.db import _get_engine, _get_users_engine  # noqa: F401
from frontend.models import *  # noqa: F401, F403
