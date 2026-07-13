import re
from difflib import SequenceMatcher

def clean_str(s):
    if not s: return ""
    s = str(s).lower()
    s = re.sub(r'[^a-z0-9]', '', s)
    s = re.sub(r'^\d+', '', s)
    for w in ['todos', 'pbbjun26', 'pbbabr26', 'site', 'lancamentosanteriores', 'pesquisagoogle']:
        s = s.replace(w, '')
    return s

def match_score(utm, api):
    u = clean_str(utm)
    a = clean_str(api)
    if not u or not a: return 0
    if u in a or a in u: return 1.0
    return SequenceMatcher(None, u, a).ratio()

utms = {
    '00-cadastrados-pbb-anteriores': 24,
    '00-viu-videos-pre-quali-pbb-jun-26': 72,
    '01-caiu-na-pag-de-captura-pbb-jun-26': 8,
    '01-termos-banco-do-brasil': 3,
    '01-viu-videos-pre-quali-lancamentos-anteriores-pbb-jun-26': 25,
    '02-viu-videos-de-captacao-180d-pbb-jun-26': 24,
    '03-viu-videos-BB-540d': 2,
    '04-viu-algum-cpl-antigo': 48,
    '05-envolvimento-60D': 3,
    '06-envolvimento-180D': 23,
    '08-mercado-setor-publico': 2,
    '09-afinidade-personalizada-concurso-banco-do-brasil-pesquisa-google': 6,
    '10-keywords-bb': 10,
    '11-Canais': 31,
    'p-max': 27
}

apis = [
    'Afinidade Personalizada (Concurso Banco do Brasil) - Pesquisa Google',
    'uservertical::80226',
    '11 - Canais Concorrentes',
    '[Felipe Graton] Envolvimento [TODOS] - 180D',
    '[Felipe Graton] Envolvimento [TODOS] - 90D',
    'Viu vídeos de captação V2 [PBB-JUN-26] - 180D',
    'Viu vídeos de captação V1 [PBB-JUN-26] - 180D',
    '[SITE] Caiu Pág. de Captura [PBB-JUN-26] - 180D',
    '[SITE] Cadastrados [PBB-JUN-26] - 180D',
    '[Felipe Graton] Envolvimento [TODOS] - 60D'
]

print("Matches:")
for api in apis:
    best_match = None
    best_score = 0
    for utm in utms.keys():
        score = match_score(utm, api)
        if score > best_score:
            best_score = score
            best_match = utm
    
    sales = utms[best_match] if best_score > 0.6 else 0
    print(f"API: {api[:40]:<40} -> UTM: {str(best_match)[:30]:<30} (Score: {best_score:.2f}, Sales: {sales})")
