fetch('http://127.0.0.1:8000/api/watchlists').then(res => res.json()).then(wlData => {
  let combined = [];
  if (wlData && Array.isArray(wlData.watchlists)) {
    combined.push(...wlData.watchlists.map((wl) => ({
      id: wl.slug,
      label: `[Watchlist] ${wl.name}`,
      type: 'watchlist',
      replacement: wl.slug
    })));
  }
  console.log(combined);
});
