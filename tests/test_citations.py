"""Formatted-citation engine (inc 106) — citeproc-js rendering via the bundled CSL styles.

Requires the build toolchain (Node + the pinned `citeproc`; `npm install`/`npm ci`). Output is deterministic
for the pinned citeproc version + bundled style files, so we assert concrete substrings + the in-text marker.
"""

from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient

from app.backend.api.app import create_app
from app.backend.citations import render, style_provenance, style_store
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper

PAPER_CSL = {
    "type": "article-journal",
    "title": "Attention is all you need",
    "author": [
        {"family": "Vaswani", "given": "Ashish"},
        {"family": "Shazeer", "given": "Noam"},
        {"family": "Parmar", "given": "Niki"},
    ],
    "issued": {"date-parts": [[2017]]},
    "container-title": "Advances in Neural Information Processing Systems",
    "volume": "30",
    "page": "5998-6008",
}

CUSTOM_CSL = """<?xml version="1.0" encoding="utf-8"?>
<style xmlns="http://purl.org/net/xbiblio/csl" class="in-text" version="1.0">
  <info>
    <title>Callosum Test Style</title>
    <id>https://example.test/styles/callosum-test-style</id>
    <link href="https://example.test/styles/callosum-test-style" rel="self"/>
    <updated>2026-07-24T00:00:00+00:00</updated>
    <category citation-format="author-date"/>
    <category field="psychology"/>
    <summary>A custom style used only by the hermetic test suite.</summary>
  </info>
  <citation>
    <layout prefix="(" suffix=")">
      <names variable="author"><name form="short"/></names>
      <date variable="issued" prefix=", "><date-part name="year"/></date>
    </layout>
  </citation>
  <bibliography>
    <layout suffix=".">
      <names variable="author"><name/></names>
      <text variable="title" prefix=". "/>
    </layout>
  </bibliography>
</style>
"""

NOTE_POSITION_CSL = """<?xml version="1.0" encoding="utf-8"?>
<style xmlns="http://purl.org/net/xbiblio/csl" class="note" version="1.0">
  <info>
    <title>Callosum Note Position Test</title>
    <id>https://example.test/styles/callosum-note-position-test</id>
    <link href="https://example.test/styles/callosum-note-position-test" rel="self"/>
    <updated>2026-07-24T00:00:00+00:00</updated>
    <category citation-format="note"/>
  </info>
  <citation near-note-distance="2">
    <layout delimiter="; ">
      <choose>
        <if position="ibid-with-locator">
          <text value="IBID-WITH-LOCATOR"/>
          <text variable="locator" prefix=":"/>
        </if>
        <else-if position="ibid">
          <text value="IBID"/>
        </else-if>
        <else-if position="subsequent">
          <choose>
            <if position="near-note">
              <text value="NEAR"/>
            </if>
            <else>
              <text value="SUBSEQUENT"/>
            </else>
          </choose>
        </else-if>
        <else>
          <text value="FIRST"/>
          <text variable="title" prefix=":"/>
        </else>
      </choose>
    </layout>
  </citation>
  <bibliography>
    <layout><text variable="title"/></layout>
  </bibliography>
</style>
"""


def _dependent_csl(parent: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<style xmlns="http://purl.org/net/xbiblio/csl" version="1.0" default-locale="en-GB">
  <info>
    <title>Callosum Dependent Test Style</title>
    <id>https://example.test/styles/callosum-dependent-test</id>
    <link href="https://example.test/styles/callosum-dependent-test" rel="self"/>
    <link href="{parent}" rel="independent-parent"/>
    <updated>2026-07-24T00:00:00+00:00</updated>
  </info>
</style>
"""


def _make_paper(temp_db_url: str) -> int:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="Attention is all you need", csl_json=PAPER_CSL)
    engine.dispose()
    return pid


def test_render_apa_author_date(temp_db_url: str) -> None:
    pid = _make_paper(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post("/citations/render", json={"paper_ids": [pid], "style": "apa", "locale": "en-US"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["style"] == "apa"
    item = d["items"][0]
    assert item["in_text"] == "(Vaswani et al., 2017)"  # APA author-date in-text
    assert "Vaswani, A." in item["reference_text"] and "2017" in item["reference_text"]
    assert (
        "<i>" in item["reference_html"] and "<div" not in item["reference_html"]
    )  # sanitized: italics kept, divs dropped
    assert "Attention is all you need" in d["bibliography_text"]


def test_render_ieee_numeric(temp_db_url: str) -> None:
    pid = _make_paper(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post("/citations/render", json={"paper_ids": [pid], "style": "ieee"})
    assert r.status_code == 200, r.text
    assert r.json()["items"][0]["in_text"] == "[1]"  # numeric in-text


def test_styles_endpoint(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    d = client.get("/citations/styles").json()
    ids = {s["id"] for s in d["styles"]}
    assert {"apa", "ieee", "modern-language-association", "chicago-author-date"} <= ids
    assert d["default_style"] == "apa" and "en-US" in d["locales"]
    apa = next(style for style in d["styles"] if style["id"] == "apa")
    assert "psychology" in apa["fields"]
    assert apa["citation_format"] == "author-date"
    assert apa["independent"] is True and apa["installed"] is True


def test_style_catalog_searches_csl_metadata(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    assert [style["id"] for style in client.get("/citations/styles?q=psychology").json()["styles"]] == ["apa"]
    assert [style["id"] for style in client.get("/citations/styles?q=MLA").json()["styles"]] == [
        "modern-language-association"
    ]
    assert [style["id"] for style in client.get("/citations/styles?q=numeric science").json()["styles"]] == ["nature"]
    assert client.get("/citations/styles", params={"q": "x" * 121}).status_code == 422


def test_style_preview_uses_fixed_examples(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post("/citations/styles/preview", json={"style": "apa", "locale": "en-US"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["example_only"] is True
    assert "Rivera & Chen, 2024" in data["citations"][0]
    assert "An example study of collaborative writing" in data["bibliography_text"]
    assert client.post("/citations/styles/preview", json={"style": "missing", "locale": "en-US"}).status_code == 422
    assert client.post("/citations/styles/preview", json={"style": "apa", "locale": "fr-FR"}).status_code == 422


def test_style_preferences_persist_default_favorites_and_recents(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.put(
        "/citations/styles/preferences",
        json={
            "style": "ieee",
            "locale": "en-GB",
            "favorite": True,
            "set_default": True,
            "mark_used": True,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["default_style"] == "ieee"
    assert data["default_locale"] == "en-GB"
    assert data["favorite_style_ids"] == ["ieee"]
    assert data["recent_style_ids"] == ["ieee"]
    ieee = next(style for style in data["styles"] if style["id"] == "ieee")
    assert ieee["favorite"] is True and ieee["recent_rank"] == 0 and ieee["application_default"] is True

    client.put(
        "/citations/styles/preferences",
        json={"style": "apa", "locale": "en-US", "mark_used": True},
    )
    data = client.get("/citations/styles").json()
    assert data["default_style"] == "ieee"  # using a document style does not change the application default
    assert data["recent_style_ids"] == ["apa", "ieee"]

    data = client.put(
        "/citations/styles/preferences",
        json={"style": "ieee", "locale": "en-GB", "favorite": False},
    ).json()
    assert data["favorite_style_ids"] == []
    assert (
        client.put(
            "/citations/styles/preferences",
            json={"style": "missing", "locale": "en-US"},
        ).status_code
        == 422
    )


def test_install_custom_style_catalog_preview_and_render(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    response = client.post(
        "/citations/styles/install",
        json={"filename": "callosum-test.csl", "csl": CUSTOM_CSL},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    installed = data["install"]
    assert installed["action"] == "installed"
    style = installed["style"]
    expected_hash = hashlib.sha256(style["canonical_id"].encode("utf-8")).hexdigest()[:8]
    assert style["id"] == f"custom-callosum-test-style-{expected_hash}"
    assert style["full_title"] == "Callosum Test Style"
    assert style["custom"] is True and style["source"] == "custom"
    assert style["canonical_id"] == "https://example.test/styles/callosum-test-style"
    assert style["provenance"]["source_type"] == "local_file"
    assert style["provenance"]["source_name"] == "callosum-test.csl"
    assert style["provenance"]["installed_at"]
    assert (style_store.custom_styles_dir() / f"{style['id']}.csl").is_file()

    assert [row["id"] for row in client.get("/citations/styles?q=hermetic psychology").json()["styles"]] == [
        style["id"]
    ]
    preferences = client.put(
        "/citations/styles/preferences",
        json={
            "style": style["id"],
            "locale": "en-GB",
            "favorite": True,
            "set_default": True,
            "mark_used": True,
        },
    )
    assert preferences.status_code == 200, preferences.text
    assert preferences.json()["default_style"] == style["id"]
    assert preferences.json()["favorite_style_ids"] == [style["id"]]
    assert preferences.json()["recent_style_ids"] == [style["id"]]
    preview = client.post(
        "/citations/styles/preview",
        json={"style": style["id"], "locale": "en-US"},
    )
    assert preview.status_code == 200, preview.text
    assert "Rivera" in preview.json()["citations"][0]

    pid = _make_paper(temp_db_url)
    rendered = client.post(
        "/citations/render",
        json={"paper_ids": [pid], "style": style["id"], "locale": "en-US"},
    )
    assert rendered.status_code == 200, rendered.text
    assert rendered.json()["items"][0]["in_text"] == "(Vaswani, Shazeer, Parmar, 2017)"


def test_custom_style_duplicate_and_explicit_update(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    first = client.post("/citations/styles/install", json={"filename": "test.csl", "csl": CUSTOM_CSL}).json()
    style_id = first["install"]["style"]["id"]

    duplicate = client.post("/citations/styles/install", json={"filename": "test.csl", "csl": CUSTOM_CSL})
    assert duplicate.status_code == 200
    assert duplicate.json()["install"]["action"] == "already_installed"

    changed = CUSTOM_CSL.replace("Callosum Test Style", "Callosum Test Style Updated")
    preflight = client.post("/citations/styles/validate", json={"filename": "test.csl", "csl": changed})
    assert preflight.status_code == 200
    assert preflight.json()["valid"] is True
    assert preflight.json()["install"]["action"] == "update_available"
    conflict = client.post("/citations/styles/install", json={"filename": "test.csl", "csl": changed})
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == {
        "code": "update_available",
        "style_id": style_id,
        "title": "Callosum Test Style Updated",
        "message": "Callosum Test Style Updated is already installed with different CSL content",
    }
    updated = client.post(
        "/citations/styles/install",
        json={"filename": "test.csl", "csl": changed, "replace": True},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["install"]["action"] == "updated"
    assert updated.json()["install"]["style"]["id"] == style_id
    assert updated.json()["install"]["style"]["full_title"] == "Callosum Test Style Updated"


def test_custom_style_export_preserves_legacy_id_on_another_device(
    temp_db_url: str,
    tmp_path,
    monkeypatch,
) -> None:
    legacy_id = "custom-legacy-callosum-test"
    style_store.write_custom_style(legacy_id, CUSTOM_CSL)
    client = TestClient(create_app(db_url=temp_db_url))

    exported = client.get(f"/citations/styles/{legacy_id}/export")
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-type"].startswith("application/vnd.citationstyles.style+xml")
    assert exported.headers["content-disposition"] == f'attachment; filename="{legacy_id}.csl"'
    assert f"<!-- callosum-style-id: {legacy_id} -->" in exported.text
    assert "callosum-style-id:" not in (style_store.custom_styles_dir() / f"{legacy_id}.csl").read_text(
        encoding="utf-8"
    )

    monkeypatch.setenv("CALLOSUM_SETTINGS_PATH", str(tmp_path / "other-device" / "app-settings.json"))
    reimported = client.post(
        "/citations/styles/install",
        json={"filename": f"{legacy_id}.csl", "csl": exported.text},
    )
    assert reimported.status_code == 200, reimported.text
    assert reimported.json()["install"]["style"]["id"] == legacy_id
    stored = style_store.custom_styles_dir() / f"{legacy_id}.csl"
    assert stored.read_text(encoding="utf-8") == CUSTOM_CSL

    duplicate = client.post(
        "/citations/styles/install",
        json={"filename": f"{legacy_id}.csl", "csl": exported.text},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["install"]["action"] == "already_installed"


def test_custom_style_removal_protects_default_and_cleans_preferences(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    installed = client.post(
        "/citations/styles/install",
        json={"filename": "test.csl", "csl": CUSTOM_CSL},
    ).json()["install"]["style"]
    style_id = installed["id"]
    client.put(
        "/citations/styles/preferences",
        json={
            "style": style_id,
            "locale": "en-US",
            "favorite": True,
            "set_default": True,
            "mark_used": True,
        },
    )

    refused = client.delete(f"/citations/styles/{style_id}")
    assert refused.status_code == 409
    assert "Choose another application default" in refused.json()["detail"]
    assert style_store.style_exists(style_id)

    client.put(
        "/citations/styles/preferences",
        json={"style": "apa", "locale": "en-US", "set_default": True, "mark_used": True},
    )
    removed = client.delete(f"/citations/styles/{style_id}")
    assert removed.status_code == 200, removed.text
    data = removed.json()
    assert style_id not in {style["id"] for style in data["styles"]}
    assert style_id not in data["favorite_style_ids"]
    assert style_id not in data["recent_style_ids"]
    assert not style_store.style_exists(style_id)
    assert style_provenance.provenance_for(style_id) is None

    pid = _make_paper(temp_db_url)
    assert (
        client.post(
            "/citations/render",
            json={"paper_ids": [pid], "style": style_id},
        ).status_code
        == 422
    )


def test_custom_style_removal_refuses_bundled_missing_and_installed_parent(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/citations/styles/apa/export").status_code == 409
    assert client.delete("/citations/styles/apa").status_code == 409
    assert client.get("/citations/styles/custom-missing/export").status_code == 404
    assert client.delete("/citations/styles/custom-missing").status_code == 404

    parent = client.post(
        "/citations/styles/install",
        json={"filename": "parent.csl", "csl": CUSTOM_CSL},
    ).json()["install"]["style"]
    dependent = client.post(
        "/citations/styles/install",
        json={
            "filename": "dependent.csl",
            "csl": _dependent_csl("https://example.test/styles/callosum-test-style"),
        },
    ).json()["install"]["style"]
    refused = client.delete(f"/citations/styles/{parent['id']}")
    assert refused.status_code == 409
    assert dependent["id"] in refused.json()["detail"]
    assert client.delete(f"/citations/styles/{dependent['id']}").status_code == 200
    assert client.delete(f"/citations/styles/{parent['id']}").status_code == 200


def test_custom_style_rejects_malformed_or_misplaced_portable_marker(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    malformed = CUSTOM_CSL.replace(
        "  <info>",
        "  <info>\n    <!-- callosum-style-id: custom-spoof -->",
    )
    response = client.post(
        "/citations/styles/validate",
        json={"filename": "spoof.csl", "csl": malformed},
    )
    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert "malformed or misplaced" in response.json()["error"]


def test_custom_dependent_style_resolves_installed_parent(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    dependent = _dependent_csl("http://www.zotero.org/styles/apa")
    installed = client.post(
        "/citations/styles/install",
        json={"filename": "dependent.csl", "csl": dependent},
    )
    assert installed.status_code == 200, installed.text
    style = installed.json()["install"]["style"]
    assert style["independent"] is False
    assert style["parent_style"] == "apa"
    preview = client.post(
        "/citations/styles/preview",
        json={"style": style["id"], "locale": "en-GB"},
    )
    assert preview.status_code == 200, preview.text
    assert "Rivera & Chen, 2024" in preview.json()["citations"][0]

    missing = _dependent_csl("https://example.test/styles/not-installed").replace(
        "callosum-dependent-test", "callosum-missing-parent"
    )
    response = client.post(
        "/citations/styles/install",
        json={"filename": "missing-parent.csl", "csl": missing},
    )
    assert response.status_code == 422
    assert "uninstalled parent" in response.json()["detail"]


@pytest.mark.parametrize(
    ("filename", "csl", "detail"),
    [
        ("style.xml", CUSTOM_CSL, "Choose a .csl"),
        ("style.csl", "", None),
        ("style.csl", "<style>", "Invalid XML"),
        ("style.csl", "<!DOCTYPE style><style/>", "DTD or entity"),
        ("style.csl", "<style>" + ("<x>" * 101) + ("</x>" * 101) + "</style>", "nested too deeply"),
        ("style.csl", CUSTOM_CSL.replace("<title>Callosum Test Style</title>", ""), "needs a title"),
        (
            "style.csl",
            CUSTOM_CSL.replace("https://example.test/styles/callosum-test-style", "not-a-url"),
            "must be an http(s) URL",
        ),
        ("style.csl", CUSTOM_CSL.replace('class="in-text"', 'class="invalid"'), "class must be"),
        (
            "style.csl",
            CUSTOM_CSL.replace("<citation>", "<citation-missing>").replace("</citation>", "</citation-missing>"),
            "needs a citation layout",
        ),
    ],
)
def test_custom_style_validation_failures(
    temp_db_url: str,
    filename: str,
    csl: str,
    detail: str | None,
) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    response = client.post("/citations/styles/install", json={"filename": filename, "csl": csl})
    assert response.status_code == 422
    if detail:
        assert detail in str(response.json()["detail"])


@pytest.mark.parametrize(
    ("csl", "detail"),
    [
        (
            CUSTOM_CSL.replace('<layout prefix="("', '<layout unsupported="yes" prefix="("'),
            "CSL 1.0.2 schema validation failed",
        ),
        (
            CUSTOM_CSL.replace('<text variable="title" prefix=". "/>', '<text macro="missing-macro"/>'),
            "CSL macro validation failed",
        ),
    ],
)
def test_custom_style_full_schema_and_macro_validation(
    temp_db_url: str,
    csl: str,
    detail: str,
) -> None:
    response = TestClient(create_app(db_url=temp_db_url)).post(
        "/citations/styles/install",
        json={"filename": "invalid.csl", "csl": csl},
    )
    assert response.status_code == 422
    assert detail in str(response.json()["detail"])


def test_duplicate_style_creates_independent_personal_copy(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    dependent = client.post(
        "/citations/styles/install",
        json={"filename": "dependent.csl", "csl": _dependent_csl("http://www.zotero.org/styles/apa")},
    ).json()["install"]["style"]

    response = client.post(
        f"/citations/styles/{dependent['id']}/duplicate",
        json={"title": "Editable Journal Copy"},
    )
    assert response.status_code == 200, response.text
    copied = response.json()["install"]["style"]
    assert copied["id"] != dependent["id"]
    assert copied["full_title"] == "Editable Journal Copy"
    assert copied["independent"] is True
    assert copied["parent_style"] is None
    assert copied["canonical_id"].startswith("https://callosum.local/styles/")
    assert copied["provenance"]["source_type"] == "duplicate"
    assert copied["provenance"]["source_style_id"] == dependent["id"]
    assert style_store.style_exists(dependent["id"])
    assert (
        client.post(
            "/citations/styles/preview",
            json={"style": copied["id"], "locale": "en-US"},
        ).status_code
        == 200
    )


def test_personal_style_source_editor_validates_previews_and_saves(
    temp_db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    installed = client.post(
        "/citations/styles/install",
        json={"filename": "editable.csl", "csl": CUSTOM_CSL},
    ).json()["install"]["style"]
    style_id = installed["id"]
    source = client.get(f"/citations/styles/{style_id}/source")
    assert source.status_code == 200, source.text
    loaded = source.json()
    assert loaded["csl"] == CUSTOM_CSL
    assert len(loaded["revision"]) == 64

    edited = CUSTOM_CSL.replace("Callosum Test Style", "Callosum Edited Style").replace(
        '<layout prefix="(" suffix=")">', '<layout prefix="[" suffix="]">'
    )
    validated = client.post(
        f"/citations/styles/{style_id}/source/validate",
        json={"csl": edited, "locale": "en-US"},
    )
    assert validated.status_code == 200, validated.text
    assert validated.json()["preview"]["citations"][0].startswith("[")
    assert style_store.style_path(style_id).read_text(encoding="utf-8") == CUSTOM_CSL

    saved = client.put(
        f"/citations/styles/{style_id}/source",
        json={
            "csl": edited,
            "expected_revision": loaded["revision"],
            "locale": "en-US",
        },
    )
    assert saved.status_code == 200, saved.text
    data = saved.json()
    assert data["editor"]["saved"] is True
    assert data["editor"]["preview"]["citations"][0].startswith("[")
    edited_style = next(style for style in data["styles"] if style["id"] == style_id)
    assert edited_style["full_title"] == "Callosum Edited Style"
    assert edited_style["canonical_id"] == installed["canonical_id"]
    assert edited_style["provenance"]["source_type"] == "local_file"
    assert edited_style["provenance"]["locally_modified_at"]
    assert data["editor"]["source"]["revision"] != loaded["revision"]

    stale = client.put(
        f"/citations/styles/{style_id}/source",
        json={
            "csl": edited.replace("Callosum Edited Style", "Stale Edit"),
            "expected_revision": loaded["revision"],
            "locale": "en-US",
        },
    )
    assert stale.status_code == 409
    assert "changed after this editor was opened" in stale.json()["detail"]

    from app.backend.citations import style_editor

    current = client.get(f"/citations/styles/{style_id}/source").json()
    concurrent = edited.replace("Callosum Edited Style", "Concurrent Edit")
    real_preview = style_editor.preview_style_xml

    def mutate_during_preview(style_xml: str, locale: str) -> dict:
        style_store.write_custom_style(style_id, concurrent)
        return real_preview(style_xml, locale)

    monkeypatch.setattr(style_editor, "preview_style_xml", mutate_during_preview)
    raced = client.put(
        f"/citations/styles/{style_id}/source",
        json={
            "csl": edited.replace("Callosum Edited Style", "Racing Edit"),
            "expected_revision": current["revision"],
            "locale": "en-US",
        },
    )
    assert raced.status_code == 409
    assert "changed during validation" in raced.json()["detail"]
    assert style_store.style_path(style_id).read_text(encoding="utf-8") == concurrent


def test_personal_style_source_editor_preserves_editability_boundary(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/citations/styles/apa/source").status_code == 409

    dependent = client.post(
        "/citations/styles/install",
        json={"filename": "dependent.csl", "csl": _dependent_csl("http://www.zotero.org/styles/apa")},
    ).json()["install"]["style"]
    refused = client.get(f"/citations/styles/{dependent['id']}/source")
    assert refused.status_code == 409
    assert "Duplicate this dependent" in refused.json()["detail"]

    installed = client.post(
        "/citations/styles/install",
        json={"filename": "editable.csl", "csl": CUSTOM_CSL},
    ).json()["install"]["style"]
    source = client.get(f"/citations/styles/{installed['id']}/source").json()
    changed_id = CUSTOM_CSL.replace(
        "https://example.test/styles/callosum-test-style",
        "https://example.test/styles/different-identity",
    )
    response = client.put(
        f"/citations/styles/{installed['id']}/source",
        json={
            "csl": changed_id,
            "expected_revision": source["revision"],
            "locale": "en-US",
        },
    )
    assert response.status_code == 422
    assert "CSL id cannot change" in response.json()["detail"]
    assert style_store.canonical_id(style_store.style_path(installed["id"])) == installed["canonical_id"]


def test_custom_style_cannot_replace_bundled_style(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    bundled = CUSTOM_CSL.replace(
        "https://example.test/styles/callosum-test-style",
        "http://www.zotero.org/styles/apa",
    )
    response = client.post(
        "/citations/styles/install",
        json={"filename": "pretend-apa.csl", "csl": bundled, "replace": True},
    )
    assert response.status_code == 422
    assert "bundled style" in response.json()["detail"]


def test_custom_style_payload_is_bounded(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    response = client.post(
        "/citations/styles/install",
        json={"filename": "oversized.csl", "csl": "x" * (style_store.MAX_CSL_BYTES + 1)},
    )
    assert response.status_code == 422


def test_custom_style_validation_preflight_reports_expected_errors_without_http_failure(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    response = client.post(
        "/citations/styles/validate",
        json={"filename": "broken.csl", "csl": "<not-csl/>"},
    )
    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert "CSL <style>" in response.json()["error"]


def test_locally_tampered_custom_style_fails_soft(temp_db_url: str) -> None:
    directory = style_store.custom_styles_dir()
    directory.mkdir(parents=True)
    (directory / "custom-tampered.csl").write_text("<not-valid", encoding="utf-8")
    client = TestClient(create_app(db_url=temp_db_url))
    assert "custom-tampered" not in {style["id"] for style in client.get("/citations/styles").json()["styles"]}
    pid = _make_paper(temp_db_url)
    response = client.post(
        "/citations/render",
        json={"paper_ids": [pid], "style": "custom-tampered"},
    )
    assert response.status_code == 422
    assert "invalid XML" in response.json()["detail"]


def test_render_validation(temp_db_url: str) -> None:
    pid = _make_paper(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post("/citations/render", json={"paper_ids": [pid], "style": "not-a-style"}).status_code == 422
    assert (
        client.post("/citations/render", json={"paper_ids": [999999], "style": "apa"}).status_code == 422
    )  # no live papers


def test_engine_unavailable_returns_503(temp_db_url: str, monkeypatch) -> None:
    pid = _make_paper(temp_db_url)
    # Simulate the citeproc dependency being absent → the route degrades to 503, never 500.
    monkeypatch.setattr(render, "_CITEPROC", render.PROJECT_ROOT / "node_modules" / "__absent__")
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post("/citations/render", json={"paper_ids": [pid], "style": "apa"}).status_code == 503


# ── document render (inc 107): position-aware in-text — numbering + disambiguation ──────────────────────

_DOC_ITEMS = {
    "a": {
        "id": "a",
        "type": "article-journal",
        "title": "Attention",
        "author": [{"family": "Vaswani", "given": "A"}],
        "issued": {"date-parts": [[2017]]},
        "container-title": "NeurIPS",
    },
    "b": {
        "id": "b",
        "type": "article-journal",
        "title": "BERT",
        "author": [{"family": "Devlin", "given": "J"}],
        "issued": {"date-parts": [[2019]]},
        "container-title": "NAACL",
    },
    "c": {
        "id": "c",
        "type": "article-journal",
        "title": "GPT",
        "author": [{"family": "Radford", "given": "A"}],
        "issued": {"date-parts": [[2018]]},
        "container-title": "OpenAI",
    },
}


def _cluster(cid: str, item_key: str) -> dict:
    return {"citationID": cid, "items": [_DOC_ITEMS[item_key]]}


def test_render_document_ieee_numbering_and_renumber(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    # Document order A,B,C → numbers follow appearance: A=[1] B=[2] C=[3].
    r = client.post(
        "/citations/render-document",
        json={"style": "ieee", "citations": [_cluster("A", "a"), _cluster("B", "b"), _cluster("C", "c")]},
    )
    assert r.status_code == 200, r.text
    d = r.json()
    by_id = {c["citationID"]: c["text"] for c in d["citations"]}
    assert by_id == {"A": "[1]", "B": "[2]", "C": "[3]"}
    assert len(d["bibliography_text"].splitlines()) == 3
    assert d["bibliography_entry_ids"] == [["a"], ["b"], ["c"]]

    # Reverse the document order → the SAME citation renumbers by its new position.
    r2 = client.post(
        "/citations/render-document",
        json={"style": "ieee", "citations": [_cluster("C", "c"), _cluster("B", "b"), _cluster("A", "a")]},
    )
    assert r2.status_code == 200, r2.text
    by_id2 = {c["citationID"]: c["text"] for c in r2.json()["citations"]}
    assert by_id2 == {"C": "[1]", "B": "[2]", "A": "[3]"}  # A was [1], now [3]


def test_render_document_returns_validated_doi_link_spans(temp_db_url: str) -> None:
    item = {**_DOC_ITEMS["a"], "DOI": "10.1234/callosum.test"}
    response = TestClient(create_app(db_url=temp_db_url)).post(
        "/citations/render-document",
        json={"style": "apa", "citations": [{"citationID": "A", "items": [item]}]},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    entry = data["bibliography_text"].splitlines()[0]
    assert len(data["bibliography_links"]) == 1
    assert len(data["bibliography_links"][0]) == 1
    link = data["bibliography_links"][0][0]
    assert link["url"] == "https://doi.org/10.1234/callosum.test"
    assert entry[link["start"] : link["start"] + link["length"]] == "https://doi.org/10.1234/callosum.test"
    assert "<a" not in data["bibliography_html"][0]  # established sanitized-HTML contract remains unchanged


def test_render_document_links_title_when_style_omits_doi_text(temp_db_url: str) -> None:
    title = "Deterministic Title Linking Across Styles"
    item = {
        **_DOC_ITEMS["a"],
        "title": title,
        "volume": "12",
        "page": "10-20",
        "DOI": "10.1234/title-link",
    }
    response = TestClient(create_app(db_url=temp_db_url)).post(
        "/citations/render-document",
        json={"style": "nature", "citations": [{"citationID": "A", "items": [item]}]},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    entry = data["bibliography_text"].splitlines()[0]
    assert "10.1234/title-link" not in entry
    assert data["bibliography_links"] == [
        [
            {
                "start": entry.index(title),
                "length": len(title),
                "url": "https://doi.org/10.1234/title-link",
            }
        ]
    ]


def test_bibliography_link_spans_reject_unsafe_or_credentialed_destinations() -> None:
    html = (
        'Unsafe <a href="javascript:alert(1)">javascript</a>; '
        '<a href="https://user:secret@example.test/private">credentialed</a>; '
        '<a href="https://example.test/safe">safe link</a>.'
    )
    start = render._to_text(html).index("safe link")
    assert render._bibliography_link_spans(html) == [
        {"start": start, "length": 9, "url": "https://example.test/safe"},
    ]
    assert render._validated_external_url("https://example.test/" + "x" * 2048) is None


def test_bibliography_title_link_fails_plain_on_unsafe_ambiguous_or_transformed_metadata() -> None:
    item = {
        "id": "a",
        "title": "A Unique Title",
        "URL": "https://example.test/source",
    }
    html = "<div>Author. A Unique Title. Journal.</div>"
    expected = [{"start": 8, "length": 14, "url": "https://example.test/source"}]
    assert render._bibliography_title_link_span(html, ["a"], {"a": item}) == expected
    assert render._bibliography_title_link_span(html.lower(), ["a"], {"a": item}) == expected
    assert render._bibliography_title_link_span(f"{html} A Unique Title.", ["a"], {"a": item}) == []
    assert render._bibliography_title_link_span("<div>Author. A Shortened Title.</div>", ["a"], {"a": item}) == []
    assert render._bibliography_title_link_span(html, ["a", "b"], {"a": item}) == []
    assert (
        render._bibliography_title_link_span(
            html,
            ["a"],
            {"a": {**item, "URL": "https://user:secret@example.test/source"}},
        )
        == []
    )
    assert (
        render._bibliography_title_destination({**item, "DOI": "doi:10.1234/title?link"})
        == "https://doi.org/10.1234/title%3Flink"
    )

    visible = '<div>A Unique Title. <a href="https://example.test/id">visible id</a>.</div>'
    visible_start = render._to_text(visible).index("visible id")
    assert render._bibliography_links(visible, ["a"], {"a": item}) == [
        {"start": visible_start, "length": 10, "url": "https://example.test/id"}
    ]


def test_render_document_apa_disambiguation(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    s1 = {
        "id": "s1",
        "type": "article-journal",
        "title": "Alpha",
        "author": [{"family": "Smith", "given": "J"}],
        "issued": {"date-parts": [[2020]]},
        "container-title": "J1",
    }
    s2 = {
        "id": "s2",
        "type": "article-journal",
        "title": "Beta",
        "author": [{"family": "Smith", "given": "J"}],
        "issued": {"date-parts": [[2020]]},
        "container-title": "J2",
    }
    r = client.post(
        "/citations/render-document",
        json={
            "style": "apa",
            "citations": [
                {"citationID": "x", "items": [s1]},
                {"citationID": "y", "items": [s2]},
            ],
        },
    )
    assert r.status_code == 200, r.text
    by_id = {c["citationID"]: c["text"] for c in r.json()["citations"]}
    assert by_id["x"] == "(Smith, 2020a)"  # same-author/year disambiguated across the document
    assert by_id["y"] == "(Smith, 2020b)"


def test_render_document_validation(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    bad = client.post("/citations/render-document", json={"style": "not-a-style", "citations": [_cluster("A", "a")]})
    assert bad.status_code == 422


def test_render_document_note_indexes_reach_citeproc(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    citations = [
        {**_cluster("first", "a"), "noteIndex": 1},
        {**_cluster("other", "b"), "noteIndex": 2},
        {**_cluster("subsequent", "a"), "noteIndex": 3},
    ]
    r = client.post(
        "/citations/render-document",
        json={"style": "chicago-notes-bibliography", "citations": citations},
    )
    assert r.status_code == 200, r.text
    by_id = {c["citationID"]: c["text"] for c in r.json()["citations"]}
    assert "Vaswani" in by_id["first"]
    assert by_id["subsequent"] != by_id["first"]


def test_imported_note_style_renders_exact_ibid_near_and_subsequent_positions(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    installed = client.post(
        "/citations/styles/install",
        json={"filename": "callosum-note-position-test.csl", "csl": NOTE_POSITION_CSL},
    )
    assert installed.status_code == 200, installed.text
    style_id = installed.json()["install"]["style"]["id"]

    def note(cid: str, item_key: str, note_index: int, locator: str | None = None) -> dict:
        item = {**_DOC_ITEMS[item_key]}
        if locator is not None:
            item.update({"locator": locator, "label": "page"})
        return {"citationID": cid, "items": [item], "noteIndex": note_index}

    rendered = client.post(
        "/citations/render-document",
        json={
            "style": style_id,
            "citations": [
                note("first", "a", 1, "10"),
                note("ibid", "a", 2, "10"),
                note("ibid-locator", "a", 3, "11"),
                note("intervening", "b", 4),
                note("near", "a", 5),
                note("far", "a", 8),
            ],
        },
    )
    assert rendered.status_code == 200, rendered.text
    by_id = {citation["citationID"]: citation["text"] for citation in rendered.json()["citations"]}
    assert by_id == {
        "first": "FIRST:Attention",
        "ibid": "IBID",
        "ibid-locator": "IBID-WITH-LOCATOR:11",
        "intervening": "FIRST:BERT",
        "near": "NEAR",
        "far": "SUBSEQUENT",
    }


@pytest.mark.parametrize("note_index", [-1, 5001, 1.5, True])
def test_render_document_rejects_invalid_note_index(temp_db_url: str, note_index: object) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post(
        "/citations/render-document",
        json={"style": "chicago-notes-bibliography", "citations": [{**_cluster("A", "a"), "noteIndex": note_index}]},
    )
    assert r.status_code == 422


@pytest.mark.parametrize(
    "note_indexes",
    [
        [0, 1],
        [1, 0],
        [2, 1],
    ],
)
def test_render_document_rejects_mixed_or_descending_note_indexes(temp_db_url: str, note_indexes: list[int]) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    citations = [
        {**_cluster(f"c{position}", "a"), "noteIndex": note_index} for position, note_index in enumerate(note_indexes)
    ]
    response = client.post(
        "/citations/render-document",
        json={"style": "chicago-notes-bibliography", "citations": citations},
    )
    assert response.status_code == 422


def test_render_document_allows_multiple_clusters_in_one_note(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    response = client.post(
        "/citations/render-document",
        json={
            "style": "chicago-notes-bibliography",
            "citations": [
                {**_cluster("first", "a"), "noteIndex": 1},
                {**_cluster("same-note", "b"), "noteIndex": 1},
                {**_cluster("next-note", "a"), "noteIndex": 2},
            ],
        },
    )
    assert response.status_code == 200, response.text
    assert [citation["citationID"] for citation in response.json()["citations"]] == [
        "first",
        "same-note",
        "next-note",
    ]


# ── per-occurrence cite properties (P0 phase 3, backlog #33/#34): locator/prefix/suffix/suppress-author/
# author-only actually reach citeproc-js, via CitationItem → citeproc_runner.js's buildCitationItem ──────────


def test_render_document_locator_and_label(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    item = {**_DOC_ITEMS["a"], "locator": "12", "label": "page"}
    r = client.post(
        "/citations/render-document", json={"style": "apa", "citations": [{"citationID": "A", "items": [item]}]}
    )
    assert r.status_code == 200, r.text
    text = r.json()["citations"][0]["text"]
    assert "12" in text  # the locator value renders somewhere in the in-text citation
    assert text != "(Vaswani, 2017)"  # differs from the no-locator baseline


def test_render_document_prefix_suffix(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    item = {**_DOC_ITEMS["a"], "prefix": "see ", "suffix": " (emphasis added)"}
    r = client.post(
        "/citations/render-document", json={"style": "apa", "citations": [{"citationID": "A", "items": [item]}]}
    )
    assert r.status_code == 200, r.text
    text = r.json()["citations"][0]["text"]
    # citeproc wraps prefix/suffix INSIDE the citation's own parenthetical group, around the cite itself —
    # "(see Vaswani, 2017 (emphasis added))" — not appended outside the parens.
    assert text == "(see Vaswani, 2017 (emphasis added))"


def test_render_document_suppress_author(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    baseline = client.post(
        "/citations/render-document",
        json={"style": "apa", "citations": [{"citationID": "A", "items": [_DOC_ITEMS["a"]]}]},
    ).json()["citations"][0]["text"]
    item = {**_DOC_ITEMS["a"], "suppress-author": True}
    r = client.post(
        "/citations/render-document", json={"style": "apa", "citations": [{"citationID": "A", "items": [item]}]}
    )
    assert r.status_code == 200, r.text
    text = r.json()["citations"][0]["text"]
    assert "Vaswani" not in text  # author suppressed
    assert text != baseline


def test_render_document_author_only(temp_db_url: str) -> None:
    """citeproc's "author-only" renders JUST the author name, dropping the date entirely — the building block
    for a manual narrative construction ("As Vaswani showed... (2017)"), paired with a companion suppress-author
    cite for the date elsewhere. It is not itself a full "Vaswani (2017)" narrative form."""
    client = TestClient(create_app(db_url=temp_db_url))
    item = {**_DOC_ITEMS["a"], "author-only": True}
    r = client.post(
        "/citations/render-document", json={"style": "apa", "citations": [{"citationID": "A", "items": [item]}]}
    )
    assert r.status_code == 200, r.text
    text = r.json()["citations"][0]["text"]
    assert text == "Vaswani"  # no parens, no year — author name only
    assert "2017" not in text


def test_citation_item_rejects_unknown_locator_label(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    item = {**_DOC_ITEMS["a"], "locator": "1", "label": "timestamp"}  # not a real CSL locator label
    r = client.post(
        "/citations/render-document", json={"style": "apa", "citations": [{"citationID": "A", "items": [item]}]}
    )
    assert r.status_code == 422


def test_citation_item_locator_length_capped(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    item = {**_DOC_ITEMS["a"], "locator": "x" * 201}
    r = client.post(
        "/citations/render-document", json={"style": "apa", "citations": [{"citationID": "A", "items": [item]}]}
    )
    assert r.status_code == 422


# ── P1 item #11 (backlog #33/#34): bibliography editing — include an uncited "further reading" work, exclude a
# specific CITED work from the bibliography (e.g. a personal communication) — both real citeproc-js mechanisms
# (updateUncitedItems / makeBibliography's field-filter bibsection), just newly wired through this endpoint ──


def test_render_document_uncited_item_appears_in_bibliography_with_no_in_text_citation(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post(
        "/citations/render-document",
        json={
            "style": "apa",
            "citations": [_cluster("A", "a")],
            "uncited_items": [_DOC_ITEMS["c"]],
        },
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["citations"]) == 1  # only the actually-cited cluster gets an in-text render
    assert "Radford" in d["bibliography_text"]  # the uncited item ("c") still appears in the bibliography
    assert "Vaswani" in d["bibliography_text"]
    assert sorted(item_id for ids in d["bibliography_entry_ids"] for item_id in ids) == ["a", "c"]


def test_render_document_bibliography_exclude_removes_entry_but_keeps_in_text_citation(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post(
        "/citations/render-document",
        json={
            "style": "apa",
            "citations": [_cluster("A", "a"), _cluster("B", "b")],
            "bibliography_exclude_ids": ["b"],
        },
    )
    assert r.status_code == 200, r.text
    d = r.json()
    by_id = {c["citationID"]: c["text"] for c in d["citations"]}
    assert "Devlin" in by_id["B"]  # the excluded work's in-text citation still renders
    assert "Devlin" not in d["bibliography_text"]  # but it's gone from the bibliography
    assert "Vaswani" in d["bibliography_text"]  # the non-excluded work is unaffected
    assert d["bibliography_entry_ids"] == [["a"]]


def test_render_document_uncited_item_missing_id_rejected(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post(
        "/citations/render-document",
        json={"style": "apa", "citations": [_cluster("A", "a")], "uncited_items": [{"title": "No id"}]},
    )
    assert r.status_code == 422


def test_render_document_bibliography_editing_fields_are_optional(temp_db_url: str) -> None:
    """Existing callers (no uncited_items/bibliography_exclude_ids at all) are completely unaffected — the
    additive-fields contract the security-audit addendum relies on."""
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post("/citations/render-document", json={"style": "apa", "citations": [_cluster("A", "a")]})
    assert r.status_code == 200, r.text
