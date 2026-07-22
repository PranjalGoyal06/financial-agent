import React, { useState, useEffect, useRef } from 'react';

interface StockResult {
  symbol: string;
  name: string;
}

interface StockSearchProps {
  onSelect: (symbol: string, name: string) => void;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';

const SearchIcon = () => (
  <svg
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <circle cx="11" cy="11" r="8"></circle>
    <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
  </svg>
);

export const StockSearch: React.FC<StockSearchProps> = ({ onSelect }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<StockResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      setIsOpen(false);
      return;
    }

    let cancelled = false;
    const timer = setTimeout(() => {
      const endpoints = [
        `/api/search/stocks?q=${encodeURIComponent(query)}`,
        `${API_BASE_URL}/api/search/stocks?q=${encodeURIComponent(query)}`,
      ];

      const fetchResults = async () => {
        for (const endpoint of endpoints) {
          try {
            const res = await fetch(endpoint);
            const contentType = res.headers.get('content-type') ?? '';

            if (!res.ok || !contentType.includes('application/json')) {
              continue;
            }

            const data = await res.json();
            if (Array.isArray(data)) {
              return data;
            }
          } catch (err) {
            console.error('Error fetching stocks from', endpoint, err);
          }
        }

        return [] as StockResult[];
      };

      fetchResults().then((data) => {
        if (cancelled) return;
        setResults(data);
        setIsOpen(data.length > 0);
      });
    }, 200);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query]);

  const handleSelect = (stock: StockResult) => {
    setQuery('');
    setIsOpen(false);
    onSelect(stock.symbol, stock.name);
  };

  return (
    <div className="stock-search-wrapper" ref={wrapperRef}>
      <div className="search-bar">
        <SearchIcon />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => { if (results.length > 0) setIsOpen(true); }}
          placeholder="Search for stocks & more"
          className="search-input"
        />
      </div>
      
      {isOpen && (
        <div className="search-dropdown">
          {results.map((stock) => (
            <div
              key={stock.symbol}
              className="search-item"
              onClick={() => handleSelect(stock)}
            >
              <div className="search-item-symbol">{stock.symbol}</div>
              <div className="search-item-name">{stock.name}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
