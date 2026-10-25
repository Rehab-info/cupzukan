"""data/cups.json から「カップ酒図鑑 by 一献」のページを作るスクリプト。
使い方: python3 tools/build.py

カップ酒を足すときは data/cups.json の cups に1件追加して、このスクリプトを実行してください。
トップ(index.html)と、1本ごとのページ(cup/<id>.html)が作り直されます。
GitHub に上げると、公開の仕組みでも自動で実行されます。
assets/ の CSS・JS を直したら、下の VERSION を1つ上げてください(閲覧者のブラウザに古い版が残らなくなります)。
"""
import html
import json
import sys
from pathlib import Path

VERSION = "8"
SITE = "https://rehab-info.github.io/cupzukan/"  # このサイトの住所(リポジトリ名を変えたらここを直す)
IKKON = "https://rehab-info.github.io/ikkon/"
KURATABI = "https://rehab-info.github.io/kuratabi/"
SAKAZUKI = IKKON + "sakazuki/"
COLUMN = IKKON + "column/cup.html"

ROOT = Path(__file__).resolve().parent.parent
data = json.loads((ROOT / "data/cups.json").read_text(encoding="utf-8"))
cups = data["cups"]
e = html.escape

# 宮城のエリア(蔵旅と同じ分け方)
AREAS = ["仙台・県央", "県南", "塩竈", "大崎・加美・遠田", "栗原・登米", "石巻・気仙沼"]
REGIONS = ["宮城", "東北", "関東", "新潟・北陸", "東海", "近畿", "中国・四国", "九州"]
CLS = {"junmai": "純米", "ginjo": "吟醸", "honjozo": "本醸造", "futsu": "普通酒"}
TYPE = {"kun": "薫酒", "sou": "爽酒", "jun": "醇酒", "juku": "熟酒"}
# 日本酒の温度の呼び名(一般的な目安)
TEMPS = [("雪冷え", "5℃"), ("花冷え", "10℃"), ("涼冷え", "15℃"), ("常温", "20℃"), ("ぬる燗", "40℃"), ("上燗", "45℃"), ("熱燗", "50℃")]
TEMP_NAMES = [t for t, _ in TEMPS]
KAN = {"ぬる燗", "上燗", "熱燗"}
COLD = {"雪冷え", "花冷え", "涼冷え"}

# 打ち間違いでカップが黙って消えたりページが壊れたりしないよう、先に確かめる
REQUIRED = ["id", "name", "short", "brewery", "pref", "region", "spec", "cls", "type", "sweet", "body", "temps", "best", "pairing", "label", "oneliner", "note", "buyNote", "seen", "sources"]
errors, seen = [], set()
for i, c in enumerate(cups, start=1):
    where = c.get("id") or f"{i}番目のカップ"
    errors += [f"{where}: 「{k}」がありません" for k in REQUIRED if c.get(k) in (None, "", [])]
    if c.get("id") in seen:
        errors.append(f"{where}: 同じ id が2つあります")
    seen.add(c.get("id"))
    if c.get("id") and not all(ch.isalnum() or ch == "-" for ch in c["id"]):
        errors.append(f"{where}: id は英数字とハイフンだけにしてください")
    if c.get("region") not in REGIONS:
        errors.append(f"{where}: region は {' / '.join(REGIONS)} のどれかにしてください")
    if c.get("region") == "宮城" and c.get("area") not in AREAS:
        errors.append(f"{where}: 宮城のカップは area を {' / '.join(AREAS)} のどれかにしてください")
    if c.get("status") not in (None, "now"):
        errors.append(f"{where}: status は、いまも売っていると確かめたときだけ \"now\" にしてください")
    if c.get("cls") not in CLS:
        errors.append(f"{where}: cls は {' / '.join(CLS)} のどれかにしてください")
    if c.get("type") not in TYPE:
        errors.append(f"{where}: type は {' / '.join(TYPE)} のどれかにしてください")
    for k in ("sweet", "body"):
        if not isinstance(c.get(k), (int, float)) or not -2 <= c[k] <= 2:
            errors.append(f"{where}: {k} は -2 から 2 の数にしてください")
    for t in c.get("temps", []):
        if t not in TEMP_NAMES:
            errors.append(f"{where}: 温度「{t}」は {' / '.join(TEMP_NAMES)} のどれかにしてください")
    if c.get("best") and c.get("best") not in c.get("temps", []):
        errors.append(f"{where}: best は temps の中から選んでください")
    for j, s in enumerate(c.get("sources", []), start=1):
        if not s.get("title") or not str(s.get("url", "")).startswith("http"):
            errors.append(f"{where}: 情報のもと{j}に title と url(http〜)を入れてください")
if errors:
    print("data/cups.json を直してください:")
    print("\n".join("  - " + x for x in errors))
    sys.exit(1)

order = {r: i for i, r in enumerate(REGIONS)}
aorder = {a: i for i, a in enumerate(AREAS)}
cups.sort(key=lambda c: (order[c["region"]], aorder.get(c.get("area"), 0), c["pref"], c["brewery"], c.get("status") != "now", c["id"]))
miyagi = [c for c in cups if c["region"] == "宮城"]
others = [c for c in cups if c["region"] != "宮城"]
now_n = sum(c.get("status") == "now" for c in miyagi)


def cup_art(c, label=True):
    """ガラスのカップの絵。ラベルの色はタイプの色、文字は銘柄の短い名前"""
    lab = f'<span class="cup-lab{" long" if len(c["short"]) >= 5 else ""}"><b>{"".join(f"<span>{e(ch)}</span>" for ch in c["short"])}</b><small>一合</small></span>' if label else ""
    return (f'<div class="cup cup-{c["type"]}" aria-hidden="true"><span class="cup-lid"></span>'
            f'<span class="cup-glass"><span class="cup-sake"></span>{lab}</span></div>')


def drinks(c):
    """絞り込み用の飲み方:冷やして・燗で"""
    out = []
    if COLD & set(c["temps"]):
        out.append("cold")
    if KAN & set(c["temps"]):
        out.append("kan")
    return " ".join(out)


def taste_word(c):
    s = c["sweet"]
    return "辛口" if s >= 0.8 else "やや辛口" if s >= 0.3 else "甘口寄り" if s <= -0.5 else "中口"


def scale(left, right, v):
    pos = round((v + 2) / 4 * 100, 1)
    return f'<div class="scale"><span>{left}</span><span class="bar"><i style="left:{pos}%"></i></span><span>{right}</span></div>'


def seen_tag(c):
    """いつの情報かを示す札。いまも売っていると確かめたものは色を変える"""
    if c.get("status") == "now":
        return f'<span class="tag now">{e(c["seen"])}も販売</span>'
    return f'<span class="tag plain">{e(c["seen"])}に確認</span>'


def card(c, prefix=""):
    where = c["pref"] + (f'・{c["city"]}' if c.get("city") else "")
    return f'''        <a class="cz-card" href="{prefix}cup/{e(c["id"])}.html" data-region="{e(c["region"])}" data-area="{e(c.get("area", ""))}" data-cls="{c["cls"]}" data-drink="{drinks(c)}" data-now="{"now" if c.get("status") == "now" else ""}">
          <div class="cz-card-media">{cup_art(c)}</div>
          <div class="cz-card-body">
            <small>{e(where)} ・ {e(c["brewery"])}</small>
            <h3>{e(c["name"])}</h3>
            <p>{e(c["oneliner"])}</p>
            {scale("甘口", "辛口", c["sweet"])}
            <div class="tags"><span class="tag">{e(c["spec"])}</span><span class="tag plain">おすすめ {e(c["best"])}</span>{seen_tag(c)}</div>
          </div>
        </a>'''


def head(title, desc, url, prefix="", current=""):
    return f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(title)}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(url)}">
<meta property="og:type" content="website">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:site_name" content="カップ酒図鑑 by 一献">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Shippori+Mincho+B1:wght@600;700&family=Zen+Kaku+Gothic+New:wght@400;700&display=swap">
<link rel="stylesheet" href="{prefix}assets/style.css?v={VERSION}">
</head>
<body>
<header class="site-head">
  <div class="wrap">
    <a class="logo" href="{prefix}index.html"><span class="mark" aria-hidden="true"></span><b>カップ酒図鑑</b><small>by 一献</small></a>
    <nav class="nav"><a href="{prefix}index.html#miyagi"{' aria-current="page"' if current == "index" else ''}>図鑑</a><a href="{prefix}kura.html"{' aria-current="page"' if current == "kura" else ''}>宮城の蔵</a><a href="{prefix}index.html#guide">楽しみ方</a></nav>
  </div>
</header>
'''


FOOT = f'''<footer class="site-foot">
  <div class="wrap">
    <span>味わいや甘辛の位置は、公開されている試飲記事や販売店の紹介をもとにした目安です。各カップの「〜に確認」は、その時期に販売を確かめたという意味です。ラベルの絵は実物を写したものではなく、タイプごとの色で描いたイメージです。中身やデザイン、取り扱いは変わることがあります。情報は{e(data["updated"].replace("-", "年", 1))}月にまとめました。</span>
    <span>「ワンカップ」は大関株式会社の登録商標です。このサイトでは、一合入りのカップの日本酒を「カップ酒」と呼んでいます。</span>
    <span>お酒は20歳になってから。飲酒運転は法律で禁止されています。カップ酒図鑑は、日本酒案内「<a href="{IKKON}">一献</a>」がつくっています。</span>
  </div>
</footer>
'''


def chip(group, value, label):
    return f'<button type="button" class="chip" data-group="{group}" data-value="{e(value)}" aria-pressed="false">{e(label)}</button>'


def build_index():
    regions = [r for r in REGIONS if any(c["region"] == r for c in others)]
    m_areas = [a for a in AREAS if any(c.get("area") == a for c in miyagi)]
    m_clss = [k for k in CLS if any(c["cls"] == k for c in miyagi)]
    clss = [k for k in CLS if any(c["cls"] == k for c in others)]
    m_brew = len({c["brewery"] for c in miyagi})
    groups = "\n".join(
        f'''      <div class="cz-group" data-group>
        <h3 class="cz-group-head">{e(a)}<small>{sum(c.get("area") == a for c in miyagi)}本</small></h3>
        <div class="cz-grid">
{chr(10).join(card(c) for c in miyagi if c.get("area") == a)}
        </div>
      </div>''' for a in m_areas)
    prefs = len({c["pref"] for c in cups})
    desc = f"駅の売店や旅先で出会う、一合(180ml)のカップ酒の図鑑。宮城を中心に{len(cups)}本を、味わい・燗向き・ラベルから紹介します。"
    out = head("カップ酒図鑑 by 一献|一合で出会う日本酒", desc, SITE, current="index")
    out += f'''
<main>
  <section class="hero-c">
    <div class="wrap">
      <div class="hc-body">
        <figure class="hc-photo"><img src="images/hero.jpg?v={VERSION}" width="900" height="900" alt="富士山と青海波を背景に描いた、一合のカップ酒のイラスト" fetchpriority="high"></figure>
        <div class="hc-tate">
          <h1>片手に、<br>一合の旅。</h1>
          <p>駅の売店から、蔵の町まで。</p>
        </div>
        <nav class="hc-side" aria-label="はじめに">
          <small>宮城の{len(miyagi)}本と、全国{prefs - 1}府県の{len(others)}本</small>
          <a href="#miyagi">宮城のカップ酒</a>
          <a href="kura.html">蔵ごとのカップ酒</a>
          <a href="#cups">全国のカップ酒</a>
          <a href="#guide">燗のつけ方としまい方</a>
          <p class="hc-note"><b>一合</b>は約180ml。四合瓶のちょうど4分の1で、ひとりの晩酌にぴったりの量です。</p>
        </nav>
      </div>
    </div>
    <div class="hc-foot"><span class="hc-seal" aria-hidden="true">合</span></div>
  </section>

  <section class="section" id="miyagi">
    <div class="wrap">
      <div class="section-head"><h2>宮城の一合</h2><p>県内{m_brew}の蔵と店の{len(miyagi)}本。エリアごとに並べています</p></div>
      <div class="cz-filter" role="group" aria-label="宮城のカップ酒を絞り込む" data-for="cz-miyagi">
        <div class="cz-frow"><span>エリア</span><div class="chips">{"".join(chip("area", a, a) for a in m_areas)}</div></div>
        <div class="cz-frow"><span>種類</span><div class="chips">{"".join(chip("cls", k, CLS[k]) for k in m_clss)}</div></div>
        <div class="cz-frow"><span>飲み方</span><div class="chips">{chip("drink", "cold", "冷やして")}{chip("drink", "kan", "燗にして")}{chip("now", "now", "いまも売っている")}</div></div>
      </div>
      <p class="cz-count" data-count aria-live="polite">{len(miyagi)}本</p>
      <div id="cz-miyagi" class="cz-groups">
{groups}
      </div>
      <p class="cz-empty" data-empty hidden>この組み合わせのカップは見つかりませんでした。条件を1つ外してみてください。</p>
      <p class="cz-note">カップ酒は季節やキャラクターで入れ替わりが多く、ここに載せたのは2013〜2026年に販売を確かめられたものです。「いまも売っている」は2026年に販売を確かめたカップです。浦霞・一ノ蔵などの蔵は一合瓶はありますが、カップは見つかりませんでした(<a href="kura.html">蔵ごとの一覧</a>)。見かけたカップがあれば、ぜひ教えてください。</p>
    </div>
  </section>

  <section class="section" id="cups">
    <div class="wrap">
      <div class="section-head"><h2>全国のカップ酒</h2><p>地域・種類・飲み方で絞り込めます</p></div>
      <div class="cz-filter" role="group" aria-label="全国のカップ酒を絞り込む" data-for="cz-cups">
        <div class="cz-frow"><span>地域</span><div class="chips">{"".join(chip("region", r, r) for r in regions)}</div></div>
        <div class="cz-frow"><span>種類</span><div class="chips">{"".join(chip("cls", k, CLS[k]) for k in clss)}</div></div>
        <div class="cz-frow"><span>飲み方</span><div class="chips">{chip("drink", "cold", "冷やして")}{chip("drink", "kan", "燗にして")}</div></div>
      </div>
      <p class="cz-count" data-count aria-live="polite">{len(others)}本</p>
      <div class="cz-grid" id="cz-cups">
{chr(10).join(card(c) for c in others)}
      </div>
      <p class="cz-empty" data-empty hidden>この組み合わせのカップはまだありません。条件を1つ外してみてください。</p>
    </div>
  </section>

  <section class="section" id="guide">
    <div class="wrap">
      <div class="section-head"><h2>一合の楽しみ方</h2><p>カップのまま、温めて、しまって、集める</p></div>
      <div class="cz-guide">
        <article>
          <h3>燗をつける</h3>
          <p>カップ酒はカップのまま温められます。</p>
          <ul>
            <li>電子レンジでは、<b>金属のふたを必ず外して</b>から。家庭用(<span class="num">600W</span>)で<span class="num">1分</span>以内が目安です。</li>
            <li>香りを残したいときは、ふたを外してお湯を張った鍋に浸ける「湯せん」で、ゆっくり温めます。</li>
            <li>人肌の<span class="num">40℃</span>前後はやわらかく、<span class="num">45℃</span>前後の上燗は香りが立ちます。</li>
          </ul>
        </article>
        <article>
          <h3>しまう</h3>
          <ul>
            <li>カップには賞味期限の代わりに製造年月が書かれています。半年から1年のうちに飲むのが目安です。</li>
            <li>透明なガラスは光に弱いので、日の当たらない涼しい場所に。夏は冷蔵庫が安心です。</li>
            <li>「要冷蔵」と書かれた生酒のカップは、必ず冷蔵庫へ。</li>
          </ul>
        </article>
        <article>
          <h3>集める</h3>
          <p>カップ酒の楽しみは、土地ごとのラベル。旅先の駅や道の駅で、その土地のカップを1本ずつ手に取ってみてください。</p>
          <p>飲んだカップは「<a href="{SAKAZUKI}">さかづき帳</a>」に記録しておくと、自分だけの一合の地図ができます。</p>
        </article>
      </div>
      <div class="cz-history">
        <b>1964</b>
        <p>東京オリンピックの開会式と同じ10月10日に、一合瓶をそのまま器にしたカップ酒が初めて売り出されました。旅先や移動中に、そのまま飲める日本酒のはじまりです。</p>
      </div>
    </div>
  </section>

  <section class="section">
    <div class="wrap">
      <div class="section-head"><h2>一献のなかま</h2></div>
      <div class="cz-series">
        <a href="{IKKON}"><b>一献</b><span>全国の名酒を、味わい・料理・温度から探す</span></a>
        <a href="{KURATABI}"><b>蔵旅 by 一献</b><span>宮城の酒蔵をたずねる旅のしおり</span></a>
        <a href="{SAKAZUKI}"><b>さかづき帳 by 一献</b><span>飲んだ日本酒とカップ酒を記録するアプリ</span></a>
      </div>
    </div>
  </section>
</main>

{FOOT}<script src="assets/app.js?v={VERSION}"></script>
</body>
</html>
'''
    (ROOT / "index.html").write_text(out, encoding="utf-8")


def temps_bar(c):
    items = []
    for name, deg in TEMPS:
        cls = "best" if name == c["best"] else "on" if name in c["temps"] else ""
        items.append(f'<li class="{cls}"><b>{name}</b><span>{deg}</span></li>' if cls else f'<li><b>{name}</b><span>{deg}</span></li>')
    return '<ol class="cz-temps" aria-label="向く温度帯">' + "".join(items) + "</ol>"


def build_cup(c):
    url = f'{SITE}cup/{c["id"]}.html'
    where = c["pref"] + (f'・{c["city"]}' if c.get("city") else "")
    desc = f'{c["name"]}({c["brewery"]}・{c["pref"]})。{c["oneliner"]}'
    facts = [("種類", c["spec"]), ("蔵", c["brewery"]), ("産地", c["pref"]), ("おすすめ", c["best"])]
    extra = [(k, c[f]) for k, f in (("アルコール", "alc"), ("お米", "rice"), ("精米歩合", "polish")) if c.get(f)]
    same = [x for x in cups if x["region"] == c["region"] and x.get("area") == c.get("area") and x["id"] != c["id"]][:3]
    same += [x for x in cups if x["region"] == c["region"] and x["id"] != c["id"] and x not in same][: 3 - len(same)]
    if len(same) < 3:
        same += [x for x in cups if x["type"] == c["type"] and x["id"] != c["id"] and x not in same][: 3 - len(same)]
    sources = "".join(f'<li><a href="{e(s["url"])}" target="_blank" rel="noopener">{e(s["title"])}</a></li>' for s in c["sources"])
    out = head(f'{c["name"]}|カップ酒図鑑 by 一献', desc, url, "../")
    out += f'''
<main>
  <div class="wrap">
    <nav class="cz-crumb" aria-label="現在地"><a href="../index.html">カップ酒図鑑</a><span aria-hidden="true">›</span><a href="../index.html#{"miyagi" if c["region"] == "宮城" else "cups"}">{e(c.get("area") or c["region"])}</a><span aria-hidden="true">›</span><span>{e(c["short"])}</span></nav>
    <section class="cz-hero">
      <div class="cz-hero-cup">{cup_art(c)}</div>
      <div class="cz-hero-text">
        <p class="eyebrow">{e(where)} ・ {TYPE[c["type"]]} ・ {e(c["seen"])}{"も販売" if c.get("status") == "now" else "に確認"}</p>
        <h1>{e(c["name"])}</h1>
        {f'<span class="kana">{e(c["kana"])}</span>' if c.get("kana") else ""}
        <p class="cz-lead">{e(c["oneliner"])}</p>
        <dl class="cz-keyfacts">{"".join(f"<div><dt>{k}</dt><dd>{e(v)}</dd></div>" for k, v in facts)}</dl>
      </div>
    </section>
  </div>

  <section class="section">
    <div class="wrap cz-cols">
      <div>
        <div class="cz-block">
          <h2>味わい</h2>
          <p>{e(c["note"])}</p>
          <div class="cz-scales">{scale("甘口", "辛口", c["sweet"])}{scale("淡麗", "濃醇", c["body"])}</div>
        </div>
        <div class="cz-block">
          <h2>飲む温度</h2>
          {temps_bar(c)}
          <p class="cz-temps-note">色のついた温度帯が向いています。燗にするときは、金属のふたを外してから。</p>
        </div>
        <div class="cz-block">
          <h2>合わせたい肴</h2>
          <div class="tags">{"".join(f'<span class="tag">{e(p)}</span>' for p in c["pairing"])}</div>
        </div>
        <div class="cz-block">
          <h2>カップのデザイン</h2>
          <p>{e(c["label"])}</p>
        </div>
      </div>
      <aside class="cz-side">
        <section><h2>どこで買える</h2><p>{e(c["buyNote"])}</p><p class="cz-fine">{e(c["seen"]) + "にも販売を確かめました。" if c.get("status") == "now" else e(c["seen"]) + "に販売を確かめた情報です。いまは中身やデザインが変わったり、販売を終えたりしているかもしれません。"}</p></section>
        {f'<section><h2>くわしく</h2><dl class="cz-keyfacts" style="margin:0;grid-template-columns:repeat({len(extra)},minmax(0,1fr))">{"".join(f"<div><dt>{k}</dt><dd>{e(v)}</dd></div>" for k, v in extra)}</dl></section>' if extra else ""}
        <section><h2>飲んだら</h2><p>さかづき帳に記録して、一合の地図を広げましょう。</p><a class="cz-record" href="{SAKAZUKI}">さかづき帳をひらく</a></section>
        <section><h2>情報のもと</h2><ul class="cz-src">{sources}</ul>
          <p class="cz-fine">味わいは記事や販売店の紹介をもとにした目安です。{e(c.get("trademark", ""))}</p></section>
      </aside>
    </div>
  </section>

  <section class="section">
    <div class="wrap">
      <div class="section-head"><h2>{"近くの一合" if c["region"] == "宮城" else "ほかの一合"}</h2></div>
      <div class="cz-grid">
{chr(10).join(card(x, "../") for x in same)}
      </div>
    </div>
  </section>
</main>

{FOOT}</body>
</html>
'''
    (ROOT / "cup" / f'{c["id"]}.html').write_text(out, encoding="utf-8")


KSTAT = {"now": ("いまも買える", "now"), "past": ("以前はあった", "past"), "none": ("見つからず", "none")}


def build_kura():
    k = json.loads((ROOT / "data/kura.json").read_text(encoding="utf-8"))
    errs = [f'{x.get("name")}: status は now / past / none のどれかにしてください' for x in k["kura"] if x.get("status") not in KSTAT]
    errs += [f'{x.get("name")}: area は {" / ".join(AREAS)} のどれかにしてください' for x in k["kura"] if x.get("area") not in AREAS]
    if errs:
        print("data/kura.json を直してください:")
        print("\n".join("  - " + x for x in errs))
        sys.exit(1)
    n = {s: sum(x["status"] == s for x in k["kura"]) for s in KSTAT}
    total = len(k["kura"])

    def cups_of(brewery):
        mine = [c for c in miyagi if c["brewery"] == brewery]
        if not mine:
            return ""
        return '<ul class="kz-cups">' + "".join(
            f'<li><a href="cup/{e(c["id"])}.html">{e(c["name"])}</a><span>{e(c["seen"])}{"も販売" if c.get("status") == "now" else "に確認"}</span></li>' for c in mine) + "</ul>"

    def row(x):
        label, cls = KSTAT[x["status"]]
        return f'''        <article class="kz-row kz-{cls}" data-status="{cls}">
          <div class="kz-head"><h3>{e(x["name"])}</h3><span class="kz-badge">{label}</span></div>
          <p class="kz-meta">{e(x["city"])} ・ {e(x["brands"])}</p>
          <p>{e(x["note"])}</p>
          {cups_of(x["brewery"])}
        </article>'''

    areas = "\n".join(
        f'''      <div class="cz-group" data-group>
        <h3 class="cz-group-head">{e(a)}<small>{sum(x["area"] == a for x in k["kura"])}蔵</small></h3>
        <div class="kz-list">
{chr(10).join(row(x) for x in k["kura"] if x["area"] == a)}
        </div>
      </div>''' for a in AREAS if any(x["area"] == a for x in k["kura"]))
    others = "".join(f'''<article class="kz-row kz-past"><div class="kz-head"><h3>{e(x["name"])}</h3><span class="kz-badge">以前はあった</span></div><p class="kz-meta">{e(x["city"])}</p><p>{e(x["note"])}</p>{cups_of(x["brewery"])}</article>''' for x in k["others"])
    srcs = "".join(f'<li><a href="{e(s["url"])}" target="_blank" rel="noopener">{e(s["title"])}</a></li>' for s in k["sources"])
    desc = f"宮城の{total}の酒蔵が、いまカップ酒を出しているかを1蔵ずつ確かめた一覧。いまも買える{n['now']}蔵、以前はあった{n['past']}蔵。"
    out = head("宮城の蔵とカップ酒|カップ酒図鑑 by 一献", desc, SITE + "kura.html", current="kura")
    out += f'''
<main>
  <section class="section">
    <div class="wrap">
      <nav class="cz-crumb" aria-label="現在地" style="padding-top:0"><a href="index.html">カップ酒図鑑</a><span aria-hidden="true">›</span><span>宮城の蔵</span></nav>
      <div class="kz-intro">
        <h1>宮城の蔵とカップ酒</h1>
        <p>{e(k["basis"])}について、いまカップ酒を出しているかを1蔵ずつ確かめました。蔵の公式サイトや通販、販売店の掲載、カップ酒を買い集めた方の記録をもとにしています({e(k["checked"])}時点)。</p>
        <dl class="kz-tally">
          <div class="kz-now"><dt>いまも買える</dt><dd>{n["now"]}<small>蔵</small></dd></div>
          <div class="kz-past"><dt>以前はあった</dt><dd>{n["past"]}<small>蔵</small></dd></div>
          <div class="kz-none"><dt>見つからず</dt><dd>{n["none"]}<small>蔵</small></dd></div>
        </dl>
        <div class="kz-bar" role="img" aria-label="{total}蔵のうち、いまも買える{n['now']}蔵、以前はあった{n['past']}蔵、見つからず{n['none']}蔵">
          <i class="kz-now" style="flex:{n["now"]}"></i><i class="kz-past" style="flex:{n["past"]}"></i><i class="kz-none" style="flex:{n["none"]}"></i>
        </div>
      </div>
      <div class="cz-filter" role="group" aria-label="蔵を絞り込む" data-for="kz-areas">
        <div class="cz-frow"><span>カップ酒</span><div class="chips">{chip("status", "now", "いまも買える")}{chip("status", "past", "以前はあった")}{chip("status", "none", "見つからず")}</div></div>
      </div>
      <p class="cz-count" data-count data-unit="蔵" aria-live="polite">{total}蔵</p>
      <div id="kz-areas" class="cz-groups">
{areas}
      </div>
      <p class="cz-empty" data-empty hidden>この条件の蔵はありません。</p>
    </div>
  </section>

  <section class="section">
    <div class="wrap">
      <div class="section-head"><h2>組合の一覧のほかにも</h2><p>小さな店や、いまは名前を見かけない蔵のカップ</p></div>
      <div class="kz-list">{others}</div>
    </div>
  </section>

  <section class="section">
    <div class="wrap kz-howto">
      <h2>この一覧の見方</h2>
      <ul>
        <li><b>いまも買える</b> … 2026年に、通販や販売店の掲載で販売を確かめられた蔵。</li>
        <li><b>以前はあった</b> … 2013〜2019年ごろに販売の記録がある蔵。いまも地元のスーパーや売店に並んでいる可能性があります。カップ酒は通販に載らないことが多く、ネットだけでは確かめきれませんでした。</li>
        <li><b>見つからず</b> … 公式サイトや通販に、カップの商品が見当たらなかった蔵。180mlの一合瓶とは分けて数えています。</li>
      </ul>
      <p>店頭で見かけたカップがあれば、ぜひ教えてください。確かめて、この一覧と図鑑に足していきます。</p>
      <h2>情報のもと</h2>
      <ul class="cz-src">{srcs}</ul>
    </div>
  </section>
</main>

{FOOT}<script src="assets/app.js?v={VERSION}"></script>
</body>
</html>
'''
    (ROOT / "kura.html").write_text(out, encoding="utf-8")


(ROOT / "cup").mkdir(exist_ok=True)
for old in (ROOT / "cup").glob("*.html"):
    old.unlink()  # 消したカップのページが残らないよう、毎回作り直す
build_index()
build_kura()
for c in cups:
    build_cup(c)
print(f"{len(cups)}本のカップ酒のページを作りました(宮城 {len(miyagi)}本)")
