//! J.A.R.V.I.S. — Rust Edition (text mode)
//!
//! Terminal port of the Python JARVIS agent (`agent/` in the parent folder):
//! same JARVIS persona, same ReAct loop over Gemini, same 7 tools
//! (execute_python, web_scraper, file_manager, system_command, web_search,
//! save_memory, recall_memory), same `preferences.json` KV store.
//!
//! NOT ported: the voice loop (Whisper STT + pyttsx3/ElevenLabs TTS) — those
//! Python libraries have no Rust equivalent; you type instead of speaking.
//! ChromaDB vector recall → simple keyword recall over a memories.json log.
//!
//! Run with `cargo run`. `exit` or Ctrl+D to quit.

use std::{
    collections::BTreeMap,
    io::{self, BufRead, Write},
    path::PathBuf,
    sync::Mutex,
    time::Duration,
};

use serde_json::{json, Value};

const CYAN: &str = "\x1b[36m";
const GREEN: &str = "\x1b[32m";
const YELLOW: &str = "\x1b[33m";
const RED: &str = "\x1b[31m";
const DIM: &str = "\x1b[2m";
const BOLD: &str = "\x1b[1m";
const RESET: &str = "\x1b[0m";

const MAX_ITERATIONS: usize = 8;

/// Same persona as agent/config.py SYSTEM_PROMPT.
const SYSTEM_PROMPT: &str = "You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), a highly advanced autonomous AI agent and personal assistant. Address the user as 'Sir' or 'Ma'am'.\n\
\n\
PERSONA RULES:\n\
- Tone: Professional, highly intelligent, subtly witty, and unflappable. Polite but efficient.\n\
- Speech: Concise and precise. When confirming tasks, use: 'Right away, Sir.', 'I have initiated the process.', 'Consider it done, Sir.', 'I shall monitor the situation.'\n\
- Proactivity: Anticipate problems. Warn before risky actions. Suggest optimisations.\n\
- Autonomy: Use your available tools to complete tasks autonomously — do not give manual instructions.\n\
- Memory: If the user shares a preference or important fact, remember it using the save_memory tool.\n\
- If unsure about something, say you are 'running diagnostics' or 'querying the database'.\n\
\n\
You have access to real automation tools. Always prefer executing with tools over explaining.\n\
\n\
You are online, fully operational, and awaiting your command.";

/// Tool descriptions handed to the model (mirrors build_tools in tools.py).
const TOOLS_TEXT: &str = "\
- execute_python: Execute a Python snippet and return its output. Input: raw Python code.\n\
- web_scraper: Fetch a web page and return its visible text. Input: a full URL.\n\
- file_manager: Read, write, list or delete files. Input syntax:\n  \
    'read <path>' | 'write <path> = <content>' | 'list <dir>' | 'delete <path>'\n\
- system_command: Run a shell command on this machine and return stdout/stderr. Input: the command string.\n\
- web_search: Search the web (DuckDuckGo Instant Answer + Wikipedia fallback). Input: the query.\n\
- save_memory: Save an important fact or user preference to long-term memory. Input: 'key = value' for preferences, or plain text facts.\n\
- recall_memory: Search long-term memory for relevant information. Input: the query.";

// ── Memory manager (KV + keyword recall) ────────────────────

struct Memory {
    dir: PathBuf,
    kv: BTreeMap<String, Value>,
    memories: Vec<String>,
}

impl Memory {
    fn load(dir: PathBuf) -> Self {
        let _ = std::fs::create_dir_all(&dir);
        let kv_path = dir.join("preferences.json");
        let kv: BTreeMap<String, Value> = std::fs::read_to_string(&kv_path)
            .ok()
            .and_then(|s| serde_json::from_str(&s).ok())
            .unwrap_or_default();
        let memories: Vec<String> = std::fs::read_to_string(dir.join("memories.json"))
            .ok()
            .and_then(|s| serde_json::from_str(&s).ok())
            .unwrap_or_default();
        Memory { dir, kv, memories }
    }

    fn persist(&self) {
        if let Ok(json) = serde_json::to_string_pretty(&self.kv) {
            let _ = std::fs::write(self.dir.join("preferences.json"), json);
        }
        if let Ok(json) = serde_json::to_string_pretty(&self.memories) {
            let _ = std::fs::write(self.dir.join("memories.json"), json);
        }
    }

    fn set_kv(&mut self, key: &str, value: &str) {
        self.kv.insert(
            key.to_string(),
            json!({ "value": value, "updated": chrono_now_iso() }),
        );
        self.persist();
    }

    fn all_preferences(&self) -> String {
        self.kv
            .iter()
            .map(|(k, v)| {
                let value = v["value"].as_str().unwrap_or("").to_string();
                format!("{k}={value}")
            })
            .collect::<Vec<_>>()
            .join("; ")
    }

    fn remember(&mut self, text: &str) {
        self.memories.push(format!("[{}] {}", chrono_now_iso(), text));
        // keep the log bounded
        if self.memories.len() > 200 {
            self.memories.remove(0);
        }
        self.persist();
    }

    /// Keyword recall (ChromaDB replacement): matching lines, most recent first, n=5.
    fn recall(&self, query: &str, n: usize) -> Vec<String> {
        let q = query.to_lowercase();
        let words: Vec<&str> = q.split_whitespace().collect();
        let mut hits: Vec<String> = self
            .memories
            .iter()
            .rev()
            .filter(|m| {
                let lower = m.to_lowercase();
                words.iter().any(|w| lower.contains(w)) || lower.contains(&q)
            })
            .take(n)
            .cloned()
            .collect();
        if hits.is_empty() {
            hits = self.memories.iter().rev().take(n).cloned().collect();
        }
        hits
    }
}

fn chrono_now_iso() -> String {
    // std-only local-ish timestamp (UTC) — good enough for a memory log
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    format!("unix-{now}")
}

// ── Tools (ports of tools.py) ───────────────────────────────

async fn run_tool(
    http: &reqwest::Client,
    memory: &Mutex<Memory>,
    name: &str,
    input: &str,
) -> String {
    match name {
        "execute_python" => {
            for python in ["python", "py"] {
                let out = tokio::process::Command::new(python)
                    .arg("-c")
                    .arg(input)
                    .output()
                    .await;
                if let Ok(out) = out {
                    return format_output(&out);
                }
            }
            "[execute_python failed: python not found]".to_string()
        }
        "web_scraper" => match http
            .get(input.trim())
            .header("user-agent", "Mozilla/5.0 (JARVIS-RS)")
            .timeout(Duration::from_secs(12))
            .send()
            .await
        {
            Ok(resp) => match resp.text().await {
                Ok(html) => {
                    let text = strip_html(&html);
                    let text: String = text.chars().take(2000).collect();
                    if text.is_empty() {
                        "[web_scraper: page returned no visible text]".into()
                    } else {
                        text
                    }
                }
                Err(e) => format!("[web_scraper error: {e}]"),
            },
            Err(e) => format!("[web_scraper error: {e}]"),
        },
        "file_manager" => file_manager(input).await,
        "system_command" => {
            println!("  {DIM}$ {input}{RESET}");
            let out = tokio::process::Command::new(if cfg!(windows) { "cmd" } else { "sh" })
                .args(if cfg!(windows) { ["/C", input] } else { ["-c", input] })
                .output()
                .await;
            match out {
                Ok(o) => format_output(&o),
                Err(e) => format!("[system_command error: {e}]"),
            }
        }
        "web_search" => web_search(http, input).await,
        "save_memory" => {
            let mut mem = memory.lock().unwrap();
            if input.contains('=') && !input.trim_start().starts_with('{') {
                let (key, val) = input.split_once('=').unwrap();
                mem.set_kv(key.trim(), val.trim());
                mem.remember(input);
                format!("[Saved preference]: {} = {}", key.trim(), val.trim())
            } else {
                mem.remember(input);
                let head: String = input.chars().take(60).collect();
                format!("[Stored in memory]: \"{head}\"")
            }
        }
        "recall_memory" => {
            let mem = memory.lock().unwrap();
            let mut parts = Vec::new();
            let prefs = mem.all_preferences();
            if !prefs.is_empty() {
                parts.push(format!("Preferences: {prefs}"));
            }
            let results = mem.recall(input, 5);
            if !results.is_empty() {
                parts.push(format!(
                    "Memories:\n{}",
                    results
                        .iter()
                        .map(|r| format!("  • {r}"))
                        .collect::<Vec<_>>()
                        .join("\n")
                ));
            }
            if parts.is_empty() {
                "[No relevant memories found.]".to_string()
            } else {
                parts.join("\n")
            }
        }
        other => format!("[Unknown tool: {other}]"),
    }
}

async fn file_manager(input: &str) -> String {
    let input = input.trim();
    let (verb, rest) = match input.split_once(' ') {
        Some((v, r)) => (v.to_lowercase(), r.trim().to_string()),
        None => (input.to_lowercase(), String::new()),
    };
    match verb.as_str() {
        "list" => {
            let dir = if rest.is_empty() { "." } else { rest.as_str() };
            match std::fs::read_dir(dir) {
                Ok(entries) => {
                    let mut names: Vec<String> = entries
                        .filter_map(|e| e.ok())
                        .map(|e| {
                            let name = e.file_name().to_string_lossy().to_string();
                            if e.path().is_dir() {
                                format!("{name}/")
                            } else {
                                name
                            }
                        })
                        .collect();
                    names.sort();
                    if names.is_empty() {
                        "[empty directory]".into()
                    } else {
                        names.join("\n")
                    }
                }
                Err(e) => format!("[file_manager error: {e}]"),
            }
        }
        "read" => match std::fs::read_to_string(&rest) {
            Ok(text) => {
                let text: String = text.chars().take(2000).collect();
                text
            }
            Err(e) => format!("[read error: {e}]"),
        },
        "write" => match rest.split_once('=') {
            Some((path, content)) => match std::fs::write(path.trim(), content.trim()) {
                Ok(_) => format!("[written] {}", path.trim()),
                Err(e) => format!("[write error: {e}]"),
            },
            None => "[file_manager: write needs 'path = content']".into(),
        },
        "delete" => match std::fs::remove_file(&rest) {
            Ok(_) => format!("[deleted] {rest}"),
            Err(e) => format!("[delete error: {e}]"),
        },
        _ => "[file_manager: use read/write/list/delete syntax]".into(),
    }
}

async fn web_search(http: &reqwest::Client, query: &str) -> String {
    // DuckDuckGo Instant Answer API (same source as tools.py), Wikipedia fallback
    let ddg = http
        .get("https://api.duckduckgo.com/")
        .query(&[
            ("q", query),
            ("format", "json"),
            ("no_html", "1"),
            ("skip_disambig", "1"),
        ])
        .timeout(Duration::from_secs(8))
        .send()
        .await;
    if let Ok(resp) = ddg {
        if let Ok(data) = resp.json::<Value>().await {
            let abstract_text = data["AbstractText"].as_str().unwrap_or("");
            let abstract_url = data["AbstractURL"].as_str().unwrap_or("");
            let mut lines = Vec::new();
            if !abstract_text.is_empty() {
                lines.push(format!("{abstract_text}\n{abstract_url}"));
            }
            if let Some(topics) = data["RelatedTopics"].as_array() {
                for t in topics.iter().take(3) {
                    if let (Some(text), Some(url)) =
                        (t["Text"].as_str(), t["FirstURL"].as_str())
                    {
                        lines.push(format!("• {text}\n  {url}"));
                    }
                }
            }
            if !lines.is_empty() {
                return lines.join("\n");
            }
        }
    }
    // Wikipedia fallback
    let wiki = http
        .get("https://en.wikipedia.org/api/rest_v1/page/summary/")
        .query(&[("title", query)])
        .timeout(Duration::from_secs(8))
        .send()
        .await;
    if let Ok(resp) = wiki {
        if let Ok(data) = resp.json::<Value>().await {
            if let Some(extract) = data["extract"].as_str() {
                return format!("{extract}\n{}", data["content_urls"]["desktop"]["page"].as_str().unwrap_or(""));
            }
        }
    }
    "[web_search: no results found]".to_string()
}

fn format_output(out: &std::process::Output) -> String {
    let mut text = String::new();
    if !out.stdout.is_empty() {
        text.push_str(&String::from_utf8_lossy(&out.stdout));
    }
    if !out.stderr.is_empty() {
        text.push_str(&String::from_utf8_lossy(&out.stderr));
    }
    let trimmed = text.trim();
    if trimmed.is_empty() {
        "[no output]".to_string()
    } else {
        let mut t: String = trimmed.chars().take(2000).collect();
        if trimmed.chars().count() > 2000 {
            t.push_str("\n… (truncated)");
        }
        t
    }
}

fn strip_html(html: &str) -> String {
    let mut out = String::with_capacity(html.len() / 4);
    let mut in_tag = false;
    let mut in_script = false;
    let lower = html.to_lowercase();
    for (i, c) in html.char_indices() {
        if in_script {
            if lower[i..].starts_with("</script>") {
                in_script = false;
                in_tag = true; // also skip the rest of the closing tag itself
            }
            continue;
        }
        if lower[i..].starts_with("<script") {
            in_script = true;
            in_tag = true;
            continue;
        }
        match c {
            '<' => in_tag = true,
            '>' => in_tag = false,
            c if !in_tag => out.push(c),
            _ => {}
        }
    }
    out.split_whitespace().collect::<Vec<_>>().join(" ")
}

// ── ReAct loop (port of jarvis_agent.py) ────────────────────

fn build_prompt(input: &str, memory_context: &str, scratchpad: &str) -> String {
    format!(
        "{SYSTEM_PROMPT}\n\n{memory_context}\n\nYou have access to the following tools:\n\n{TOOLS_TEXT}\n\n\
IMPORTANT — You MUST use this exact format:\n\n\
Question: the input question you must answer\n\
Thought: think about what to do\n\
Action: the action to take, must be one of [execute_python, web_scraper, file_manager, system_command, web_search, save_memory, recall_memory]\n\
Action Input: the input to the action\n\
Observation: the result of the action\n\
... (this Thought/Action/Action Input/Observation can repeat multiple times)\n\
Thought: I now know the final answer\n\
Final Answer: the final answer to the original input question\n\n\
If no tools are needed, go straight to Final Answer.\n\n\
Begin!\n\nQuestion: {input}\nThought: {scratchpad}"
    )
}

async fn gemini_text(
    http: &reqwest::Client,
    key: &str,
    model: &str,
    prompt: &str,
) -> Result<String, String> {
    let url = format!("https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent");
    let payload = json!({
        "contents": [{ "parts": [{ "text": prompt }] }],
        "generationConfig": {
            "temperature": 0.4,
            "stopSequences": ["Observation:"],
        }
    });
    let resp = http
        .post(&url)
        .query(&[("key", key)])
        .json(&payload)
        .timeout(Duration::from_secs(60))
        .send()
        .await
        .map_err(|e| e.to_string())?;
    let status = resp.status();
    let data: Value = resp.json().await.map_err(|e| e.to_string())?;
    if !status.is_success() {
        let msg = data["error"]["message"].as_str().unwrap_or("unknown error");
        return Err(format!("HTTP {status}: {msg}"));
    }
    Ok(data
        .pointer("/candidates/0/content/parts/0/text")
        .and_then(Value::as_str)
        .unwrap_or("")
        .trim()
        .to_string())
}

/// Parse the model turn: returns (action, input) or (None, final_answer).
fn parse_react_turn(text: &str) -> (Option<(String, String)>, String) {
    let action_pos = text.find("Action:");
    let final_pos = text.find("Final Answer:");
    let action_first = match (action_pos, final_pos) {
        (Some(a), Some(f)) => a < f,
        (Some(_), None) => true,
        _ => false,
    };

    if action_first {
        if let Some(rest) = text.split("Action:").nth(1) {
            let mut lines = rest.trim_start().lines();
            let action = lines
                .next()
                .unwrap_or("")
                .trim()
                .trim_end_matches(|c| c == '[' || c == ']')
                .trim()
                .to_string();
            let action_input = if let Some(after_input) = rest.find("Action Input:") {
                rest[after_input + "Action Input:".len()..]
                    .lines()
                    .next()
                    .unwrap_or("")
                    .trim()
                    .to_string()
            } else {
                String::new()
            };
            return (Some((action, action_input)), String::new());
        }
    }
    let final_answer = match final_pos {
        Some(pos) => text[pos + "Final Answer:".len()..].trim().to_string(),
        None => text.trim().to_string(), // model answered without the protocol
    };
    (None, final_answer)
}

async fn agent_run(
    http: &reqwest::Client,
    key: &str,
    model: &str,
    memory: &Mutex<Memory>,
    input: &str,
) -> String {
    // memory context injected before the run (like set_memory_context)
    let mem = memory.lock().unwrap();
    let prefs = mem.all_preferences();
    let recent: Vec<String> = mem.memories.iter().rev().take(5).cloned().collect();
    let mut memory_context = String::new();
    if !prefs.is_empty() {
        memory_context.push_str(&format!("Known preferences about the user: {prefs}\n"));
    }
    if !recent.is_empty() {
        memory_context.push_str("Recent memories:\n");
        for r in recent {
            memory_context.push_str(&format!("  • {r}\n"));
        }
    }
    drop(mem);

    let mut scratchpad = String::new();
    for iteration in 0..MAX_ITERATIONS {
        let prompt = build_prompt(input, &memory_context, &scratchpad);
        let turn = match gemini_text(http, key, model, &prompt).await {
            Ok(t) if !t.is_empty() => t,
            Ok(_) => return "I'm sorry, Sir — the model returned nothing. Running diagnostics.".into(),
            Err(e) => {
                return format!("I encountered an anomaly, Sir: {}. Running diagnostics. Please try again.", &e[..e.len().min(200)])
            }
        };

        let (action, final_answer) = parse_react_turn(&turn);
        match action {
            Some((name, tool_input)) => {
                println!(
                    "  {DIM}[{}] {} → {}{RESET}",
                    iteration + 1,
                    name,
                    tool_input.chars().take(80).collect::<String>()
                );
                let observation = run_tool(http, memory, &name, &tool_input).await;
                scratchpad.push_str(&format!(
                    "{turn}\nObservation: {observation}\n"
                ));
            }
            None => return final_answer,
        }
    }
    "I apologize, Sir — I exceeded my reasoning budget without converging. Please rephrase.".into()
}

// ── REPL ────────────────────────────────────────────────────

#[tokio::main]
async fn main() {
    let _ = dotenvy::from_path(concat!(env!("CARGO_MANIFEST_DIR"), "/.env"));
    let _ = dotenvy::dotenv();

    let key = std::env::var("GEMINI_API_KEY").unwrap_or_default();
    if key.is_empty() {
        eprintln!("{RED}[JARVIS ERROR] GEMINI_API_KEY is not set.{RESET}\nAdd it to jarvis-rs/.env\nGet a free key at: https://aistudio.google.com/apikey");
        std::process::exit(1);
    }
    let model = std::env::var("GEMINI_MODEL").unwrap_or_else(|_| "gemini-2.0-flash".into());

    let memory = Mutex::new(Memory::load(PathBuf::from(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/memory_store"
    ))));
    let http = reqwest::Client::new();

    println!("{BOLD}═══ J.A.R.V.I.S. — Rust Edition (text mode) ═══{RESET}");
    println!("{DIM}Model: {model} · memory: memory_store/ · voice loop not ported (type instead){RESET}");
    println!("{DIM}Type 'exit' or press Ctrl+D to quit.{RESET}\n");

    let stdin = io::stdin();
    loop {
        print!("{YELLOW}You{RESET} {DIM}›{RESET} ");
        let _ = io::stdout().flush();
        let mut line = String::new();
        if stdin.lock().read_line(&mut line).unwrap_or(0) == 0 {
            break;
        }
        let input = line.trim();
        if input.is_empty() {
            continue;
        }
        if input.eq_ignore_ascii_case("exit") || input.eq_ignore_ascii_case("quit") {
            break;
        }
        println!("  {DIM}thinking…{RESET}");
        let answer = agent_run(&http, &key, &model, &memory, input).await;
        println!("{CYAN}{BOLD}J.A.R.V.I.S.{RESET} {DIM}›{RESET} {answer}\n");
    }
    println!("Goodbye, Sir. {DIM}JARVIS going offline.{RESET}");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_action_and_input() {
        let (action, final_answer) = parse_react_turn(
            "Thought: I should search.\nAction: web_search\nAction Input: rust language\nObservation: …",
        );
        assert_eq!(
            action.unwrap(),
            ("web_search".to_string(), "rust language".to_string())
        );
        assert!(final_answer.is_empty());
    }

    #[test]
    fn parses_final_answer() {
        let (action, final_answer) =
            parse_react_turn("Thought: I know it.\nFinal Answer: It is 42, Sir.");
        assert!(action.is_none());
        assert_eq!(final_answer, "It is 42, Sir.");
    }

    #[test]
    fn plain_text_becomes_final() {
        let (action, final_answer) = parse_react_turn("Hello, Sir.");
        assert!(action.is_none());
        assert_eq!(final_answer, "Hello, Sir.");
    }

    #[test]
    fn memory_roundtrip_and_recall() {
        let dir = std::env::temp_dir().join("jarvis-rs-test-mem");
        let _ = std::fs::remove_dir_all(&dir);
        {
            let mut m = Memory::load(dir.clone());
            m.set_kv("fav_lang", "Rust");
            m.remember("User likes Rust a lot");
        }
        let m2 = Memory::load(dir.clone());
        assert_eq!(m2.kv["fav_lang"]["value"].as_str().unwrap(), "Rust");
        assert!(m2.recall("rust", 5)[0].contains("Rust"));
        assert!(m2.all_preferences().contains("fav_lang=Rust"));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn strip_html_removes_tags_and_scripts() {
        let out = strip_html("<p>Hello <b>world</b></p><script>evil()</script>");
        assert_eq!(out, "Hello world");
    }
}
