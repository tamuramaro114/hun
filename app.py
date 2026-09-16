import os
import random
import pandas as pd
import streamlit as st

# ファイルパスの設定
WORDS_CSV = "words.csv"
STATS_CSV = "stats.csv"

st.set_page_config(
    page_title="韓国語 4択クイズアプリ", page_icon="📝", layout="wide"
)


# --- データロード・初期化関数 ---
@st.cache_data
def load_words():
  if not os.path.exists(WORDS_CSV):
    return pd.DataFrame(
        columns=["korean", "reading", "japanese", "part_of_speech"]
    )

  df = None
  for enc in ["utf-8-sig", "utf-8"]:
    try:
      temp_df = pd.read_csv(WORDS_CSV, encoding=enc)
      if not temp_df.empty:
        df = temp_df
        break
    except Exception:
      continue

  if df is None or df.empty:
    try:
      df = pd.read_csv(WORDS_CSV, encoding="cp932")
    except Exception:
      pass

  if df is None or df.empty:
    st.error(
        "CSVファイルを読み込めませんでした。`words.csv` の文字コードを"
        " **UTF-8** にして保存し直してください。"
    )
    return pd.DataFrame(
        columns=["korean", "reading", "japanese", "part_of_speech"]
    )

  cols = list(df.columns)
  if len(cols) >= 4:
    df.columns = [
        "korean",
        "reading",
        "japanese",
        "part_of_speech",
    ] + [f"extra_{i}" for i in range(len(cols) - 4)]
  elif len(cols) == 3:
    df["part_of_speech"] = "名詞"
    df.columns = ["korean", "reading", "japanese", "part_of_speech"]

  for c in ["korean", "reading", "japanese", "part_of_speech"]:
    if c in df.columns:
      df[c] = df[c].astype(str)

  return df


def load_stats():
  if not os.path.exists(STATS_CSV):
    words_df = load_words()
    if words_df.empty:
      return pd.DataFrame(
          columns=[
              "korean",
              "total_attempts",
              "correct_attempts",
              "accuracy",
              "recent_results",
              "recent_accuracy",
          ]
      )
    stats_data = []
    for k in words_df["korean"]:
      stats_data.append({
          "korean": k,
          "total_attempts": 0,
          "correct_attempts": 0,
          "accuracy": 0.0,
          "recent_results": "",
          "recent_accuracy": 0.0,
      })
    stats_df = pd.DataFrame(stats_data)
    stats_df.to_csv(STATS_CSV, index=False, encoding="utf-8-sig")
    return stats_df

  stats_df = None
  for enc in ["utf-8-sig", "utf-8", "cp932"]:
    try:
      stats_df = pd.read_csv(STATS_CSV, encoding=enc)
      break
    except UnicodeDecodeError:
      continue

  if stats_df is None:
    stats_df = pd.DataFrame(
        columns=[
            "korean",
            "total_attempts",
            "correct_attempts",
            "accuracy",
            "recent_results",
            "recent_accuracy",
        ]
    )

  stats_df["recent_results"] = stats_df["recent_results"].fillna("").astype(str)
  return stats_df


def update_stats(korean_word, is_correct):
  stats_df = load_stats()
  idx = stats_df[stats_df["korean"] == korean_word].index

  if len(idx) == 0:
    new_row = pd.DataFrame([{
        "korean": korean_word,
        "total_attempts": 1,
        "correct_attempts": 1 if is_correct else 0,
        "accuracy": 100.0 if is_correct else 0.0,
        "recent_results": "1" if is_correct else "0",
        "recent_accuracy": 100.0 if is_correct else 0.0,
    }])
    stats_df = pd.concat([stats_df, new_row], ignore_index=True)
  else:
    i = idx[0]
    total = int(stats_df.loc[i, "total_attempts"]) + 1
    correct = int(stats_df.loc[i, "correct_attempts"]) + (1 if is_correct else 0)
    accuracy = (correct / total) * 100.0

    recent_str = str(stats_df.loc[i, "recent_results"])
    recent_list = []
    if recent_str and recent_str.lower() != "nan":
      for x in recent_str.split(","):
        x = x.strip()
        try:
          if x != "":
            recent_list.append(int(float(x)))
        except ValueError:
          continue

    recent_list.append(1 if is_correct else 0)
    if len(recent_list) > 10:
      recent_list = recent_list[-10:]

    recent_accuracy = (
        (sum(recent_list) / len(recent_list)) * 100.0 if recent_list else 0.0
    )

    stats_df.loc[i, "total_attempts"] = total
    stats_df.loc[i, "correct_attempts"] = correct
    stats_df.loc[i, "accuracy"] = round(accuracy, 2)
    stats_df.loc[i, "recent_results"] = ",".join(map(str, recent_list))
    stats_df.loc[i, "recent_accuracy"] = round(recent_accuracy, 2)

  stats_df.to_csv(STATS_CSV, index=False, encoding="utf-8-sig")


# --- メイン画面レイアウト ---
st.title("🇰🇷 韓国語 4択クイズアプリ")

if st.sidebar.button("🔄 キャッシュをクリアして再読み込み"):
  st.cache_data.clear()
  if "quiz_pool" in st.session_state:
    del st.session_state.quiz_pool
  st.rerun()

words_df = load_words()
if words_df.empty:
  st.error(
      f"`{WORDS_CSV}` が見つからないか、データが空です。ファイルを配置してくだ"
      "さい。"
  )
  st.stop()

# サイドバー：モード選択・設定
st.sidebar.header("⚙️ 設定 & モード")
app_mode = st.sidebar.radio("メニュー", ["クイズを解く", "単語・成績一覧CSV"])

if app_mode == "クイズを解く":
  st.sidebar.subheader("出題範囲・順番の設定")

  all_pos = (
      ["すべて"] + list(words_df["part_of_speech"].dropna().unique())
      if "part_of_speech" in words_df.columns
      else ["すべて"]
  )
  selected_pos = st.sidebar.selectbox("品詞で絞り込み", all_pos)

  order_mode = st.sidebar.selectbox(
      "出題順序",
      [
          "ランダム (指定範囲から)",
          "正答率が低い順 (全体)",
          "直近正答率が低い順 (直近10回)",
          "昇順 (CSVの順)",
          "降順 (CSVの逆順)",
      ],
  )

  # 条件（品詞や順番）が変わったときにプールをリセットするための判定キー
  current_settings_key = f"{selected_pos}_{order_mode}"
  if st.session_state.get("last_settings_key") != current_settings_key:
    st.session_state.last_settings_key = current_settings_key
    if "quiz_pool" in st.session_state:
      del st.session_state.quiz_pool
    if "quiz_index" in st.session_state:
      st.session_state.quiz_index = 0
    if "is_answered" in st.session_state:
      st.session_state.is_answered = False
    if "current_target" in st.session_state:
      st.session_state.current_target = None

  # クイズの出題プールがまだ作成されていない場合のみ作成してセッションに保持する
  if "quiz_pool" not in st.session_state:
    if selected_pos != "すべて":
      filtered_words_df = words_df[words_df["part_of_speech"] == selected_pos]
    else:
      filtered_words_df = words_df

    stats_df = load_stats()
    merged_df = pd.merge(filtered_words_df, stats_df, on="korean", how="left")
    merged_df["accuracy"] = merged_df["accuracy"].fillna(0.0)
    merged_df["recent_accuracy"] = merged_df["recent_accuracy"].fillna(0.0)

    if order_mode == "ランダム (指定範囲から)":
      quiz_pool = merged_df.sample(frac=1).reset_index(drop=True)
    elif order_mode == "正答率が低い順 (全体)":
      quiz_pool = merged_df.sort_values(
          by="accuracy", ascending=True
      ).reset_index(drop=True)
    elif order_mode == "直近正答率が低い順 (直近10回)":
      quiz_pool = merged_df.sort_values(
          by="recent_accuracy", ascending=True
      ).reset_index(drop=True)
    elif order_mode == "昇順 (CSVの順)":
      quiz_pool = merged_df.reset_index(drop=True)
    else:
      quiz_pool = merged_df.iloc[::-1].reset_index(drop=True)

    st.session_state.quiz_pool = quiz_pool
    st.session_state.quiz_index = 0
    st.session_state.is_answered = False
    st.session_state.current_target = None

  quiz_pool = st.session_state.quiz_pool

  if quiz_pool.empty:
    st.warning(
        "選択された条件（品詞など）に一致する単語がありません。別の条件を選んでく"
        "ださい。"
    )
    if st.button("設定をリセット"):
      if "quiz_pool" in st.session_state:
        del st.session_state.quiz_pool
      st.rerun()
    st.stop()

  if "quiz_index" not in st.session_state:
    st.session_state.quiz_index = 0
  if "selected_answer" not in st.session_state:
    st.session_state.selected_answer = None
  if "is_answered" not in st.session_state:
    st.session_state.is_answered = False

  if st.session_state.quiz_index >= len(quiz_pool):
    st.session_state.quiz_index = 0

  current_row = quiz_pool.iloc[st.session_state.quiz_index]
  target_korean = str(current_row["korean"])
  target_japanese = str(current_row["japanese"])
  target_reading = str(current_row["reading"])

  st.subheader(
      f"問題 {st.session_state.quiz_index + 1} / {len(quiz_pool)}"
  )
  st.markdown(
      f"### 次の韓国語の意味として正しいものを選んでください: **`{target_korean}`**"
  )

  # 4択の選択肢作成
  if "current_choices" not in st.session_state or st.session_state.get(
      "current_target"
  ) != target_korean:
    other_words = words_df[words_df["japanese"] != target_japanese]
    if len(other_words) >= 3:
      dummies = other_words["japanese"].sample(n=3).tolist()
    else:
      dummies = other_words["japanese"].tolist()
      while len(dummies) < 3:
        dummies.append("ダミー")

    choices = dummies + [target_japanese]
    random.shuffle(choices)
    st.session_state.current_choices = choices
    st.session_state.current_target = target_korean
    st.session_state.is_answered = False
    st.session_state.selected_answer = None

  choices = st.session_state.current_choices

  # 未回答のときは選択肢と回答ボタンを表示
  if not st.session_state.is_answered:
    with st.form(key=f"quiz_form_{st.session_state.quiz_index}"):
      user_choice = st.radio(
          "選択肢:", choices, key=f"radio_{st.session_state.quiz_index}"
      )
      submit_button = st.form_submit_button(label="回答する")

      if submit_button:
        st.session_state.is_answered = True
        st.session_state.selected_answer = user_choice
        is_correct = user_choice == target_japanese
        update_stats(target_korean, is_correct)
        st.rerun()

  # 回答済みのときは、結果（正解/不正解）と解説、次の問題へのボタンを表示
  else:
    st.radio(
        "選択肢:",
        choices,
        index=choices.index(st.session_state.selected_answer)
        if st.session_state.selected_answer in choices
        else 0,
        disabled=True,
        key=f"disabled_radio_{st.session_state.quiz_index}",
    )

    if st.session_state.selected_answer == target_japanese:
      st.success("🎉 正解です！")
    else:
      st.error(
          f"❌ 残念！不正解です。正解は **「{target_japanese}」** です。"
      )

    st.info(f"📖 **解説**: `{target_korean}` の読みは **[{target_reading}]** です。")

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
      if st.button("次の問題へ ➡️", type="primary"):
        st.session_state.quiz_index = (st.session_state.quiz_index + 1) % len(
            quiz_pool
        )
        st.session_state.is_answered = False
        st.session_state.current_target = None
        st.rerun()
    with col2:
      if st.button("🔀 リストを再シャッフル"):
        if "quiz_pool" in st.session_state:
          del st.session_state.quiz_pool
        st.session_state.quiz_index = 0
        st.session_state.is_answered = False
        st.session_state.current_target = None
        st.rerun()
    with col3:
      if st.button("🔄 最初からやり直す"):
        st.session_state.quiz_index = 0
        st.session_state.is_answered = False
        st.session_state.current_target = None
        st.rerun()

elif app_mode == "単語・成績一覧CSV":
  st.subheader("📊 単語リスト & 成績・正答率一覧")
  stats_df = load_stats()

  combined_df = pd.merge(words_df, stats_df, on="korean", how="left")
  combined_df["accuracy"] = combined_df["accuracy"].fillna(0.0)
  combined_df["recent_accuracy"] = combined_df["recent_accuracy"].fillna(0.0)
  combined_df["total_attempts"] = combined_df["total_attempts"].fillna(0).astype(int)
  combined_df["correct_attempts"] = combined_df["correct_attempts"].fillna(0).astype(int)

  sort_by = st.selectbox(
      "並び替え基準",
      [
          "CSVのデフォルト順",
          "正答率が低い順",
          "正答率が高い順",
          "直近正答率が低い順",
          "直近正答率が高い順",
          "解答回数が多い順",
      ],
  )

  if sort_by == "正答率が低い順":
    combined_df = combined_df.sort_values(by="accuracy", ascending=True)
  elif sort_by == "正答率が高い順":
    combined_df = combined_df.sort_values(by="accuracy", ascending=False)
  elif sort_by == "直近正答率が低い順":
    combined_df = combined_df.sort_values(by="recent_accuracy", ascending=True)
  elif sort_by == "直近正答率が高い順":
    combined_df = combined_df.sort_values(by="recent_accuracy", ascending=False)
  elif sort_by == "解答回数が多い順":
    combined_df = combined_df.sort_values(by="total_attempts", ascending=False)

  display_df = combined_df[[
      "korean",
      "reading",
      "japanese",
      "part_of_speech",
      "total_attempts",
      "correct_attempts",
      "accuracy",
      "recent_accuracy",
  ]].copy()
  display_df.columns = [
      "韓国語",
      "読み",
      "日本語",
      "品詞",
      "総解答数",
      "正解数",
      "正答率(%)",
      "直近正答率(%)",
  ]

  st.dataframe(display_df, use_container_width=True)

  st.download_button(
      label="💾 統計データをCSVとしてダウンロード",
      data=stats_df.to_csv(index=False, encoding="utf-8-sig").encode(
          "utf-8-sig"
      ),
      file_name="stats_export.csv",
      mime="text/csv",
  )
