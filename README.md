# informationcollapse

情報破壊業KKの公開記録庫。**生成AIが新たに書く文書**を主とし、Sの創作遺稿、青空文庫の著作権消滅作品、複数言語の公開ページの一文が混入する作品です。

## 最初の公開

1. GitHubに **公開** リポジトリ `informationcollapse` を新規作成する。既存の `private-data` には置かない。
2. このZIPの中身をリポジトリの `main` ブランチ直下へアップロードする（ZIPファイルそのものではなく展開後のファイル）。`.github/workflows/archives.yml` も含める。多数のファイルを扱う場合はGitクライアントで一括 push する。
3. Settings → Pages → Build and deployment → Source を **GitHub Actions** に設定する。
4. [Google AI Studio](https://aistudio.google.com/apikey) で**無料枠のAPIキー**を取得し、GitHubの Settings → Secrets and variables → Actions → Repository secrets に `GEMINI_API_KEY` として登録する。公開ファイルには絶対に書かない。OpenAI APIキーは不要。
5. Actions → `Informationcollapse — write and publish` → Run workflow を一度実行する。Actionsが利用でき、権限設定が整っていれば以降はおよそ5分ごとに実行する。
6. サイトURL（ユーザー名 `poraporanekochan` の場合）は `https://poraporanekochan.github.io/informationcollapse/`。公開前にこのURLが存在するとは限らない。

## 表示仕様

- 白背景、黒字、明朝体、本文以外に小さなbit数と出典テキストのみ。
- 1秒に3書記素（見かけの文字）表示。ブラウザのバックグラウンド制限により、完全な実時間保証ではない。
- 文書生成を主とし、当該タブで5分ごとに青空文庫からの引用、10分ごとに多言語の公開情報を優先表示する。これは新たな生成ではなく、**実際に取得・保存できた公開記録**からの選択。
- Sの死後に生成したSの文章は本人の原本と表示せず、推定復元した創作として扱う。
- `公開記録bit` は `archive/YYYY/YYYYMMDD.txt` のファイルサイズ合計に8を掛けた値。転送量や世界中への拡散数ではない。

## 実際のAI生成について

- GitHub Actionsは5分ごとに外部資料の取得を試み、**AI生成は最大2時間に1回**4件の独立文書の生成を試みる。APIエラー、スケジュール遅延、アカウントの利用上限などで欠ける場合がある。無限・秒単位の更新保証ではない。
- `GEMINI_API_KEY` が設定されていない場合、**新規AI文章は生成されない**。既存の創作記録だけを表示する。画面上で「AIが書き続けている」と偽る実装は行っていない。
- APIキー以外の生成元テキスト、公開ページのURL、ライセンス情報はGitHub上に残る。
- `GEMINI_MODEL` をRepository variablesに設定するとモデルを変更できる（初期値 `gemini-3.5-flash-lite`）。**必ず無料枠に対応したモデルを選ぶこと**。
- 生成・取得内容は公開される。個人情報や秘密のプロジェクト資料を入れないこと。

## 外部文の出典

- 青空文庫：公式作品一覧から著作権消滅の作品のみ抽出し、原文の短い一文を引用。取得失敗時は引用を偽造しない。
- 多言語：MediaWiki APIから複数言語のWikipedia記事の短い一文を選択。出典・CC BY-SAライセンスURLを保存。**インターネット全体からの完全一様抽選ではない**。
- X/Instagramの投稿は、各サービスのAPI利用権限・転載条件が未確認なので初期版では取り込まない。

## 編集

- `archive/` は年別の生資料（ファイル名はYYYYMMDD.txt）。
- `data/seed.json` は架空の初期記録、`data/generated.jsonl` は実際にAIが生成した記録、`data/external.jsonl` は外部ソースから取得した引用。
- `engine/generate.py` が生成・収集・出典保存・統計を担当。
- `assets/stream.js` が閲覧用の文字表示と優先表示を担当。
- 内容が重なるほど、Sの正体が決定不可能になることを作品の主題とする。事実としての引用と創作記録をデータ上は厳密に区別する。

## 料金ゼロを優先する運用（2026年11月）

- GitHub Pagesと公開リポジトリの標準GitHub Actionsは無料の範囲で使える。GitHubの利用規約・実行時間等の制限は適用される。
- Gemini APIの無料枠にはモデル別・プロジェクト別の回数制限があり、超過するとHTTP 429などで生成をスキップする。**必ず継続生成される保証はない。**
- この版は有料OpenAI APIを一切呼び出さず、自動課金を伴う別サービスへも切り替えない。無料枠で使えるキー・モデルで運用し、Google側で有料プランを有効化しないこと。
- Gemini API無料枠に送った創作テキストはサービス改善に利用される場合がある。公開前提の架空記録だけを使い、私的な情報や未公開の個人情報を含めない。
- 動作確認: `data/stats.json` の `ai_generated_count` が増えたらGeminiで本当に生成された。`data/external.jsonl` の記録が増えれば外部からの引用取得に成功。

- 多言語の外部引用は約10分ごとに最大3件を試行する（取得失敗時は減る）。無料枠のAI生成とは独立している。
