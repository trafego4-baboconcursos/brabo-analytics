"""Junta linhas quebradas (hard wrap) em .md: cada paragrafo/item numa linha so.

Uso:
    python scripts/desquebrar_md.py docs/projetos            # so relata
    python scripts/desquebrar_md.py --write docs/projetos    # grava

Antes de gravar, confere que o HTML renderizado (markdown-it-py) fica igual; arquivo que
mudaria a renderizacao e pulado e listado. Criado em 20/11/26 (vault inteiro desquebrado).
Nao mexe em: frontmatter, blocos de codigo, comentarios HTML, tabelas, headings,
HTML, callout headers, linhas com quebra forcada (2 espacos, barra, <br>)."""
import re
import sys

LIST = re.compile(r'^\s*([-*+] |\d+[.)] )')
BLOCK_START = re.compile(r'^\s*([-*+] |\d+[.)] |```|~~~|\||#|<|\$\$|!\[\[|\[\^|\[!)')
RULE = re.compile(r'^\s*(-{3,}|\*{3,}|_{3,}|={3,})\s*$')
QUOTE = re.compile(r'^(\s*(?:>\s?)+)(.*)$')
BACKSLASH = chr(92)


def split_quote(line):
    m = QUOTE.match(line)
    return (m.group(1).replace(' ', ''), m.group(2)) if m else ('', line)


def can_join(prev, line):
    pq, pbody = split_quote(prev)
    q, body = split_quote(line)
    if pq != q:
        return False
    ps, s = pbody.strip(), body.strip()
    if not ps or not s:
        return False
    if BLOCK_START.match(body) or RULE.match(body):
        return False
    if ps.startswith(('|', '#', '```', '~~~', '<', '$$', '![[', '[!')) or RULE.match(pbody):
        return False
    if prev.endswith(('  ', BACKSLASH, '<br>', '<br/>', '<br />')):
        return False
    # 4+ espacos fora de lista = bloco de codigo indentado
    indent = len(body) - len(body.lstrip(' '))
    pindent = len(pbody) - len(pbody.lstrip(' '))
    if indent >= 4 and not LIST.match(pbody) and pindent < 2:
        return False
    return True


def unwrap(text):
    lines = text.split('\n')
    out, i, n = [], 0, 0
    if lines and lines[0].strip() == '---':
        j = 1
        while j < len(lines) and lines[j].strip() != '---':
            j += 1
        out.extend(lines[:j + 1])
        i = j + 1
    fence = None
    comment = False
    table = False
    for line in lines[i:]:
        _, body = split_quote(line)
        bs = body.strip()
        if not bs:
            table = False
        elif bs.startswith('|') and not fence and not comment:
            table = True
        if table:
            out.append(line)
            continue
        if fence:
            out.append(line)
            if bs.startswith(fence):
                fence = None
            continue
        if bs.startswith(('```', '~~~')):
            fence = bs[:3]
            out.append(line)
            continue
        if comment:
            out.append(line)
            if '-->' in line:
                comment = False
            continue
        if '<!--' in line and '-->' not in line.split('<!--', 1)[1]:
            comment = True
            out.append(line)
            continue
        if out and can_join(out[-1], line):
            out[-1] = out[-1].rstrip() + ' ' + body.lstrip()
            n += 1
        else:
            out.append(line)
    return '\n'.join(out), n



def _render_igual(antes, depois):
    try:
        from markdown_it import MarkdownIt
    except ImportError:
        sys.exit('instale markdown-it-py: pip install markdown-it-py')
    md = MarkdownIt('commonmark').enable('table')
    norm = lambda h: re.sub(r'\s+', ' ', h)
    return norm(md.render(antes)) == norm(md.render(depois))


def _arquivos(caminhos):
    import os
    for c in caminhos:
        if os.path.isdir(c):
            for raiz, _, nomes in os.walk(c, followlinks=True):
                for nome in sorted(nomes):
                    if nome.endswith('.md'):
                        yield os.path.join(raiz, nome)
        else:
            yield c


if __name__ == '__main__':
    write = '--write' in sys.argv
    tot = files = 0
    pulados = []
    for f in _arquivos([a for a in sys.argv[1:] if a != '--write']):
        raw = open(f, encoding='utf-8', newline='').read()
        crlf = '\r\n' in raw
        antes = raw.replace('\r\n', '\n')
        new, n = unwrap(antes)
        if not n:
            continue
        if not _render_igual(antes, new):
            pulados.append(f)
            continue
        tot += n
        files += 1
        print(f'{n:5d}  {f}')
        if write:
            open(f, 'w', encoding='utf-8', newline='').write(new.replace('\n', '\r\n') if crlf else new)
    print(f'TOTAL: {tot} juncoes em {files} arquivos' + ('' if write else ' (nada gravado; use --write)'))
    for f in pulados:
        print('PULADO (renderizacao mudaria):', f)
