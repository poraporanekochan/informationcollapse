# informationcollapse — 第八界 / v4

情報破壊業KKの公開記録庫。架空のA・Sの記録、実際にGemini無料枠で生成した文章、青空文庫の著作権消滅作品からの抜粋、多言語Wikipediaの短い原文を混在させる。**架空の資料と、実際に取得した引用は、必ず別々の種類・出典で記録する。**

公開サイト： https://poraporanekochan.github.io/informationcollapse/

## v4 で直したこと

1. **全文書を表示対象にする。** 従来の `data/latest.json` は抜粋だけを保持していた。v4では `data/catalog.json` と `data/shards/<kind>/<hash>.json` を生成し、`data/seed.json`・`data/generated.jsonl`・`data/external.jsonl` の**全構造化文書**を索引化する。ブラウザは必要なデータ片だけを取得する。古い日付の文書も対象に残る。
2. **重複表示を防ぐ。** IndexedDBに読んだ記録のIDを保存し、全件を一巡するまで同じIDを再選択しない。古いv3の閲覧履歴も引き継ぐ。IndexedDBが無効な環境ではlocalStorageへフォールバックする（こちらは容量に制限がある）。履歴を消した端末や異なる端末間では重複防止は共有されない。
3. **保存済み文書を消さない。** `archive/YYYY/YYYYMMDD.txt`、`data/generated.jsonl`、`data/external.jsonl` を追記する。表示用シャードだけを再生成する。重複テキストは表示索引から取り除くが、原記録は残す。
4. **自動実行の時刻をずらす。** GitHub Actionsを毎時7・22・37・52分（UTC）に予定する。GitHubのスケジューラは遅延・省略・無効化されることがあるので、時刻どおりの実行は保証できない。長時間空いた場合、次回に取得件数を増やすが、失われた過去の時点の情報を復元するものではない。
5. **成功と失敗を分ける。** `data/health.json` にGemini・青空文庫・Wikipediaの実行状況、追加件数、出典取得エラー、実行日時を残す。`data/stats.json` にはAI生成総件数などを表示する。Actionsの緑チェックはソフトウェアが正常終了したことだけを意味する。
6. **費用ゼロ優先。** OpenAI有料APIにアクセスしない。Geminiは**無料枠に対応するモデル・無料設定のプロジェクト**に限って使用する。有料請求が有効なAPIキーで課金されないことはソフトウェア側で保証できないので、Google側で有料請求を有効にしない。Geminiは最大120分に1回・最大4文書。無料枠が尽きた場合も既存文書の閲覧と公的資料収集は継続可能。
7. **検証する。** Actions実行前にPython/JavaScriptのオフラインテストを行い、公開前に索引の欠落・重複・公開bit数の不一致がないか検証する。

## 大事な区別

- 「**公開記録bit**」は `archive/` 以下のTXTファイルの実際のUTF-8バイト数×8。ウェブ全体に広がった情報量という意味ではない。
- GitHubでストックされるのは**実際に取得・生成して保存できた記録だけ**。画面でのランダム表示そのものは新たな情報の収集ではない。
- Wikipediaの抽出元はMediaWiki API。**インターネット全体・X・Instagramの無作為抽出ではない。** 引用元URLと著作権条件は各記録に残す。Wikipediaの記事にはCC BY-SAによる再利用条件がある。
- 青空文庫は著作権消滅フラグを持つ作品を選ぶが、外部サービスが取得に失敗した場合に文章を捏造しない。
- `archive/` の手書きTXTの全段落を自動で再解析するものではない。表示対象は `seed.json` と二つのJSONLに保存された構造化記録の全件。構造化記録の原本TXTも従来どおり保存する。
- ブラウザが読み込む文書は世界中の閲覧者で同一の公開ストックを共有するが、**各閲覧者の表示順は独立**している。
- 第三者が取得する文章の内容は予測・制御できない。公開前の人手による全件確認は自動化していない。個人情報や不適切な内容が混入する可能性は残るため、定期的な内容監査が必要。

## iPhone / Working Copy で更新する

1. `informationcollapse_v4_update.zip` をiPhoneに保存して解凍する。
2. ZIP内の**元のフォルダ階層を保持したまま**、既存の `informationcollapse` Gitリポジトリの直下に移す。`assets/stream.js` と `engine/generate.py` と `.github/workflows/archives.yml`、`README.md` は置き換え、`engine/catalog.py`・`engine/verify.py`・`tests/*` は新規追加。
3. **`data/` と `archive/` は削除・置き換えしない。** ZIPには意図的にこれらを含めていない。
4. Working Copyで変更をCommit→Push。
5. GitHub Actions `Informationcollapse — write and publish` の**push実行**が成功すれば、`data/catalog.json` が作られたことを確認。問題がなければ **Run workflow** を一度実行し、`data/health.json` の `new` などを確認。
6. Safariで公開サイトを再読み込み。1秒につき3文字の表示は以前と同じ。

## 動作確認用URL

- Actions: https://github.com/poraporanekochan/informationcollapse/actions
- 全件索引: https://github.com/poraporanekochan/informationcollapse/blob/main/data/catalog.json
- 稼働状況: https://github.com/poraporanekochan/informationcollapse/blob/main/data/health.json
- 公開件数: https://github.com/poraporanekochan/informationcollapse/blob/main/data/stats.json
- 外部文章: https://github.com/poraporanekochan/informationcollapse/blob/main/data/external.jsonl
- AI文章: https://github.com/poraporanekochan/informationcollapse/blob/main/data/generated.jsonl

`data/catalog.json` の `record_count` と `data/stats.json` の `unique_visible_record_count` が一致しており、Actionsの `Verify record retention and public catalogue` が緑色なら、構造化全文書の公開索引は整合している。

## 運用上の限界

- GitHub Actionsの実行はベストエフォート。公開リポジトリが60日間非アクティブの場合、スケジュールが自動無効化される可能性がある。
- GitHub Pagesは帯域・容量等のサービス上限の対象。無期限・無制限保存を保証しない。現状のTXTはGitHubの履歴に残るが、別サービスへの二重バックアップではない。
- 採録源はWikipediaと青空文庫を中心にした限定的な範囲であり、ライセンス条件やAPI規約の変化に応じたメンテナンスが必要。
- 認証情報はGitHub Secretsの `GEMINI_API_KEY` のみ。**ZIPや公開ファイルへ鍵を記載しない。**
