# GitHub CSV weather signage

構成
- `.github/workflows/update-weather.yml`: JST 05:10 / 11:10 / 17:10 に更新
- `scripts/update_weather.py`: 気象庁JSONを取得しCSV化、SVGもリポジトリへ保存
- `data/weather.csv`: 表示専用データ
- `icons/*.svg`: 表示用ローカルアイコン
- `index.html`: CSVだけを読み込む表示画面

GitHubでの手順
1. ファイル一式をリポジトリのルートへ配置してmainへコミット。
2. Settings > Pages で Deploy from a branch、main / root を選択。
3. Actionsタブで Update weather CSV を開き、Run workflowを1回実行。
4. Actionsがpushできない場合は Settings > Actions > General > Workflow permissions で Read and write permissions を許可。

注意
- cronはUTC指定。`20,2,8`時に実行し、日本時間05:10 / 11:10 / 17:10に対応。
- 表示側は気象庁へ直接アクセスせず、同一リポジトリのCSVとSVGだけを読む。
- CSV更新に失敗しても、直前に正常生成されたCSVとSVGは残る。
