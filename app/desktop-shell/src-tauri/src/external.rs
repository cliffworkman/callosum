//! Open an external URL in the user's default browser (inc 589).
//!
//! Inside the Tauri webview, the frontend's `window.open(url, "_blank")` — and an ordinary
//! `<a target="_blank" href="https://…">` — do NOT hand the URL to the system browser, so every
//! "Open article ↗" / "Open in browser" / library-resolver hand-off silently failed in the packaged app (a real
//! user clicked ~10 times and only ever got an empty new tab). This command is the single, scheme-validated seam
//! the frontend routes external URLs through; a plain browser (the dev server or the remote-access tunnel, where
//! `window.__TAURI__` is absent) keeps using `window.open`.

use tauri::AppHandle;
use tauri_plugin_opener::OpenerExt;

/// Accept only **http(s)** URLs (returning the trimmed URL) so a compromised or buggy frontend can never coerce
/// the opener into launching a `file://` path or a custom-scheme protocol handler — it can only ever open a web
/// URL, exactly like clicking a link. Kept pure (no `AppHandle`) so it is unit-testable without a running app.
fn validated_external_url(url: &str) -> Result<String, String> {
    let trimmed = url.trim();
    let lowered = trimmed.to_ascii_lowercase();
    if lowered.starts_with("https://") || lowered.starts_with("http://") {
        Ok(trimmed.to_string())
    } else {
        Err("only http(s) URLs may be opened".into())
    }
}

/// Open an http(s) URL in the system default browser. Non-http(s) schemes are rejected before the opener runs.
#[tauri::command]
pub fn open_external_url(app: AppHandle, url: String) -> Result<(), String> {
    let target = validated_external_url(&url)?;
    app.opener()
        .open_url(target, None::<&str>)
        .map_err(|error| error.to_string())
}

#[cfg(test)]
mod tests {
    use super::validated_external_url;

    #[test]
    fn accepts_http_and_https_and_rejects_other_schemes() {
        assert!(validated_external_url("https://doi.org/10.1/x").is_ok());
        assert!(validated_external_url("http://example.org").is_ok());
        // trims surrounding whitespace
        assert_eq!(
            validated_external_url("  https://doi.org/10.1/x  ").unwrap(),
            "https://doi.org/10.1/x"
        );
        // rejects every non-web scheme + a bare (schemeless) string
        for bad in [
            "file:///etc/passwd",
            "javascript:alert(1)",
            "ftp://example.org",
            "mailto:a@b.c",
            "",
            "doi.org/10.1/x",
        ] {
            assert!(validated_external_url(bad).is_err(), "should reject {bad}");
        }
    }
}
