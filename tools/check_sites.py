"""data/sites.json が、一献・蔵旅・カップ酒図鑑の3つのリポジトリで同じ内容かを確かめるスクリプト。
同じファイルを3つのリポジトリ(ikkon・kuratabi・cupzukan)に置いています。直すときは3つとも同じに直します。

使い方:
  python3 tools/check_sites.py                    … ほかの2つのリポジトリの data/sites.json を GitHub から読んで比べる
  python3 tools/check_sites.py ほかの sites.json …  手元のファイルと比べる(GitHub に出られないときの確認用)

- 書き方の誤り(項目の書き忘れ、URL が https:// で始まらない・/ で終わらない など)も確かめます。
- プルリクエストでは、ほかのリポジトリに同じ名前のブランチがあればそちらと比べます(3つを同時に直すとき用)。なければ main と比べます。
- 食い違いや書き方の誤りがあると、項目ごとに理由を表示して終了コード 1 で止まります。
- ほかのリポジトリを読めなかったとき(通信の不調など)は、確かめられなかったことを表示して止めません。
このスクリプトはサイトの公開(pages.yml)とは別に動くので、食い違っていても公開は止まりません。
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPOS = ["ikkon", "kuratabi", "cupzukan"]
SITE_KEYS = ["ikkon", "kuratabi", "sakazuki", "cupzukan"]
# GitHub 上のファイルの置き場所(独自ドメインへの移行の影響を受けない)。試験のときは SITES_CHECK_RAW で差し替えられる
RAW = os.environ.get("SITES_CHECK_RAW", "https://raw.githubusercontent.com/Rehab-info/{repo}/{ref}/data/sites.json")
IN_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"


def flat(d, prefix=""):
    """比べやすいよう、入れ子を「sites.ikkon.url」のような1段の形にする(「_」で始まる説明書きは比べない)。"""
    out = {}
    for k, v in d.items():
        if k.startswith("_"):
            continue
        key = f"{prefix}{k}"
        out.update(flat(v, key + ".") if isinstance(v, dict) else {key: v})
    return out


def lint(d):
    """書き方の誤りを探す。"""
    errs = []
    sites = d.get("sites")
    if not isinstance(sites, dict):
        return ["sites がありません"]
    for k in SITE_KEYS:
        s = sites.get(k)
        if not isinstance(s, dict):
            errs.append(f"sites.{k} がありません")
            continue
        for f in ["name", "url", "desc"]:
            if not isinstance(s.get(f), str) or not s[f].strip():
                errs.append(f"sites.{k}.{f} がありません")
        u = s.get("url", "")
        if isinstance(u, str) and u and not (u.startswith("https://") and u.endswith("/")):
            errs.append(f"sites.{k}.url は https:// で始まり / で終わる形にします(いま: {u})")
    errs += [f"sites.{k} は使われていない名前です(使えるのは {', '.join(SITE_KEYS)})" for k in sites if k not in SITE_KEYS]
    trips = d.get("kuratabiTrips")
    if not isinstance(trips, dict) or not trips:
        errs.append("kuratabiTrips がありません")
    else:
        errs += [f"kuratabiTrips.{k} の蔵の名前がありません" for k, v in trips.items() if not isinstance(v, str) or not v.strip()]
    return errs


def diff(a, b, name):
    """項目ごとに、どう違うかを書く。"""
    out = []
    for k in sorted(set(a) | set(b)):
        if k not in b:
            out.append((k, f"このリポジトリにだけあります({a[k]!r})。{name} にはありません"))
        elif k not in a:
            out.append((k, f"{name} にだけあります({b[k]!r})。このリポジトリにはありません"))
        elif a[k] != b[k]:
            out.append((k, f"値が違います。このリポジトリ: {a[k]!r} / {name}: {b[k]!r}"))
    return out


def self_name():
    repo = os.environ.get("GITHUB_REPOSITORY", "").split("/")[-1]
    return repo if repo in REPOS else ROOT.name


def fetch(repo):
    """ほかのリポジトリの sites.json を読む。同じ名前のブランチ → main の順に探す。
    返り値: (相手の名前, 中身, 通信の不調などで確かめられなかった理由, 食い違いとして扱う誤り)"""
    refs = [r for r in [os.environ.get("GITHUB_HEAD_REF"), "main"] if r]
    for ref in dict.fromkeys(refs):
        try:
            with urllib.request.urlopen(RAW.format(repo=repo, ref=ref), timeout=20) as r:
                return f"{repo} の {ref}", json.loads(r.read().decode("utf-8")), None, None
        except urllib.error.HTTPError as err:
            if err.code == 404:
                continue
            return None, None, f"{repo} を読めませんでした({err.code})", None
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            return None, None, f"{repo} を読めませんでした({err})", None
        except json.JSONDecodeError:
            return None, None, None, f"{repo} の {ref}: data/sites.json が JSON として読めません"
    return None, None, None, f"{repo}: data/sites.json がありません({' / '.join(dict.fromkeys(refs))} を探しました)"


def report(lines, kind):
    for line in lines:
        print(f"::{kind}::{line}" if IN_ACTIONS else f"  - {line}")


def summary(text):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")


try:
    mine = json.loads((ROOT / "data/sites.json").read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as err:
    sys.exit(f"data/sites.json を読めませんでした: {err}")

problems, warnings, compared = [f"このリポジトリ: {e}" for e in lint(mine)], [], []
others = []
if sys.argv[1:]:
    for p in sys.argv[1:]:
        try:
            others.append((p, json.loads(Path(p).read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError) as err:
            problems.append(f"{p} を読めませんでした: {err}")
else:
    me = self_name()
    for repo in REPOS:
        if repo == me:
            continue
        name, data, warn, err = fetch(repo)
        if warn:
            warnings.append(warn + "。この組み合わせは確かめられませんでした")
        elif err:
            problems.append(err)
        else:
            others.append((name, data))

for name, other in others:
    problems += [f"{name}: {e}" for e in lint(other)]
    d = diff(flat(mine), flat(other), name)
    problems += [f"{k}: {why}" for k, why in d]
    compared.append(name)

if warnings:
    print("確かめられなかったもの:")
    report(warnings, "warning")
if problems:
    print("data/sites.json が3つのリポジトリで食い違っているか、書き方に誤りがあります。3つとも同じ内容にそろえてください。")
    report(problems, "error")
    summary("## data/sites.json の確認\n\n食い違い・誤りがあります。\n\n| 項目と理由 |\n|---|\n" + "".join(f"| {p.replace('|', '/')} |\n" for p in problems))
    sys.exit(1)
msg = f"data/sites.json は {', '.join(compared)} と一致しています" if compared else "data/sites.json の書き方に誤りはありません(比べる相手は読めませんでした)"
print(msg)
summary(f"## data/sites.json の確認\n\n{msg}" + ("\n\n確かめられなかったもの: " + " / ".join(warnings) if warnings else ""))
