(function () {
  "use strict";

  class CallosumSiteHeader extends HTMLElement {
    connectedCallback() {
      if (this.shadowRoot) return;
      const page = this.dataset.page || "home";
      const homePrefix = page === "home" ? "" : "index.html";
      const howHref = page === "how" ? "#pipeline" : "how-it-works.html";
      const showcaseHref = page === "showcase" ? "#tour" : "showcase.html#tour";
      const demoHref = "demo/";
      const icon = document.querySelector('link[rel~="icon"]')?.href || "";
      const root = this.attachShadow({ mode: "open" });
      root.innerHTML = `
        <style>
          :host{display:block;position:sticky;top:0;z-index:100}
          *{box-sizing:border-box}
          header{background:color-mix(in srgb,#f7f4ed 90%,transparent);backdrop-filter:saturate(1.1) blur(10px);border-bottom:1px solid #ddd7cc;color:#201d18;font-family:"IBM Plex Sans",system-ui,sans-serif}
          .inner{width:min(100% - 48px,1180px);height:66px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;gap:24px}
          .brand{display:flex;align-items:center;gap:11px;text-decoration:none;color:inherit;white-space:nowrap}
          .brand img{width:34px;height:30px;object-fit:contain;display:block}
          .name{font-family:"Newsreader",Georgia,serif;font-size:24px;font-weight:600;letter-spacing:-.02em}
          nav{display:flex;align-items:center;gap:28px}
          nav a{color:#625d54;text-decoration:none;font-size:14.5px;transition:color .18s,transform .18s}
          nav a:hover,nav a[aria-current="page"]{color:#37306f}
          .demo-link{color:#37306f;font-weight:600}
          .github{display:inline-flex;align-items:center;gap:7px}
          .github svg{width:16px;height:16px}
          .download{background:#37306f;color:#fff;padding:9px 15px;border-radius:7px;font-weight:500}
          .download:hover{color:#fff;transform:translateY(-1px);background:#26215a}
          a:focus-visible{outline:2.5px solid #37306f;outline-offset:3px;border-radius:3px}
          @media(max-width:860px){nav{gap:14px}nav a:not(.demo-link):not(.github):not(.download){display:none}.inner{width:min(100% - 28px,1180px)}}
          @media(max-width:480px){.github{display:none}.inner{height:60px}.name{font-size:22px}}
        </style>
        <header>
          <div class="inner">
            <a class="brand" href="${homePrefix}#top" aria-label="Callosum home">
              ${icon ? `<img src="${icon}" alt="" width="34" height="30">` : ""}
              <span class="name">Callosum</span>
            </a>
            <nav aria-label="Primary">
              <a href="${howHref}" ${page === "how" ? 'aria-current="page"' : ""}>How it works</a>
              <a href="${homePrefix}#features">Features</a>
              <a href="${showcaseHref}" ${page === "showcase" ? 'aria-current="page"' : ""}>Showcase</a>
              <a class="demo-link" href="${demoHref}">Demo</a>
              <a href="${homePrefix}#privacy">Privacy</a>
              <a class="github" href="https://github.com/cliffworkman/callosum" target="_blank" rel="noopener">
                <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 .5a11.5 11.5 0 0 0-3.64 22.41c.58.11.79-.25.79-.56v-2c-3.2.7-3.88-1.37-3.88-1.37-.53-1.34-1.29-1.7-1.29-1.7-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.2 1.77 1.2 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.2-3.1-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11 11 0 0 1 5.8 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.75.81 1.2 1.84 1.2 3.1 0 4.42-2.69 5.39-5.25 5.68.41.36.78 1.05.78 2.12v3.14c0 .31.21.68.8.56A11.5 11.5 0 0 0 12 .5Z"/></svg>
                GitHub
              </a>
              <a class="download" href="${homePrefix}#download">Download</a>
            </nav>
          </div>
        </header>`;
    }
  }

  if (!customElements.get("callosum-site-header")) {
    customElements.define("callosum-site-header", CallosumSiteHeader);
  }
})();
