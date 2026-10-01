//! Paths crossing the Chrome/Edge native-messaging registration boundary on Windows.
use std::path::{Component, Path, Prefix};

pub fn for_browser(path: &Path) -> Result<&Path, &'static str> {
    // Unlike blindly stripping \\?\, dunce preserves verbatim paths whose names or
    // length would change meaning under ordinary Win32 rules. Those cannot safely
    // be handed to Chrome's cmd.exe launcher. Network/device namespaces are also
    // unsupported here; the packaged per-user install is on a local drive.
    let path = dunce::simplified(path);
    if path.is_absolute()
        && matches!(path.components().next(), Some(Component::Prefix(p)) if matches!(p.kind(), Prefix::Disk(_)))
    {
        Ok(path)
    } else {
        Err("Browser Capture needs a standard local Windows installation path. Reinstall Callosum in a shorter local folder without special filenames, then Prepare again.")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalizes_executable_and_registry_paths_without_losing_unicode() {
        for name in ["callosum-connector.exe", "org.callosum.connector.json"] {
            let plain = format!(r"C:\Users\Zoë\Callosum QA\connector\{name}");
            let verbatim = format!(r"\\?\{plain}");
            assert_eq!(
                for_browser(Path::new(&verbatim)).unwrap(),
                Path::new(&plain)
            );
            assert_eq!(for_browser(Path::new(&plain)).unwrap(), Path::new(&plain));
        }
    }

    #[test]
    fn refuses_paths_that_cannot_safely_cross_the_browser_boundary() {
        for path in [
            r"connector\host.exe",
            r"C:connector\host.exe",
            r"\connector\host.exe",
            r"\\server\share\host.exe",
            r"\\?\UNC\server\share\host.exe",
            r"\\.\C:\host.exe",
            r"\\?\C:\folder.\host.exe",
            r"\\?\C:\folder \host.exe",
            r"\\?\C:\NUL\host.exe",
            r"\\?\C:\folder\..\host.exe",
            r"\\?\C:\host.exe:stream",
        ] {
            assert!(for_browser(Path::new(path)).is_err(), "{path}");
        }
        let too_long = format!(r"\\?\C:\{}\host.exe", "a".repeat(260));
        assert!(for_browser(Path::new(&too_long)).is_err());
    }
}
