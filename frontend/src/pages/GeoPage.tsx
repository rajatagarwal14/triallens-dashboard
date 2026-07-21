import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Circle, Pane, Tooltip as LeafletTooltip, Popup, useMap, useMapEvents } from 'react-leaflet'
import {
  Search, Map, List, AlertCircle, ChevronRight, Edit3, Info, CheckCircle2, Database,
  Layers, Activity, MapPin, Building2, ArrowLeft, ExternalLink, Flame, Crosshair, Cpu,
} from 'lucide-react'
import { TopBar } from '@/components/Layout/TopBar'
import { CoverageBadge } from '@/components/common/CoverageBadge'
import { ErrorState } from '@/components/common/ErrorState'
import { api } from '@/api/client'
import { useSharedSearch, filterParams } from '@/context/SearchContext'
import { ActiveFilters } from '@/components/common/ActiveFilters'
import type { Site } from '@/types'
import { clsx } from 'clsx'
import 'leaflet/dist/leaflet.css'
// Accurate official India outline (full J&K, Ladakh, Arunachal Pradesh; reaches
// 37.08°N / 97.39°E) — dissolved from official district boundaries. The world
// GeoJSON below draws India's de-facto borders (Kashmir truncated), so we strip
// its India feature and draw this one on top instead.
import INDIA_OFFICIAL from '@/data/india-official.json'

const WORLD_GEOJSON_URL = 'https://raw.githubusercontent.com/holtzy/D3-graph-gallery/master/DATA/world.geojson'

/**
 * CT.gov country names → this GeoJSON's properties.name. Without this, the
 * biggest markets (US, UK) silently render as empty polygons. Verified against
 * the actual GeoJSON polygon names.
 */
const COUNTRY_TO_GEOJSON: Record<string, string> = {
  'United States': 'USA',
  'United Kingdom': 'England',          // this low-res set only has England
  'Czechia': 'Czech Republic',
  'Turkey (Türkiye)': 'Turkey',
  'Russian Federation': 'Russia',
  'Korea, Republic of': 'South Korea',
  "Korea, Democratic People's Republic of": 'North Korea',
  'Iran, Islamic Republic of': 'Iran',
  'Viet Nam': 'Vietnam',
  'Serbia': 'Republic of Serbia',
  "Lao People's Democratic Republic": 'Laos',
  'Brunei Darussalam': 'Brunei',
  'Syrian Arab Republic': 'Syria',
  'Venezuela, Bolivarian Republic of': 'Venezuela',
  'Bolivia, Plurinational State of': 'Bolivia',
  'Moldova, Republic of': 'Moldova',
  'North Macedonia': 'Macedonia',
  'Tanzania': 'United Republic of Tanzania',
}

// CT.gov countries with no polygon in this GeoJSON (city/SAR) — still shown as
// site dots, just not as filled choropleth regions.
const NO_POLYGON = new Set(['Hong Kong', 'Singapore', 'Unknown'])

type MapMode = 'density' | 'prevalence' | 'intensity'

function toGeoName(ctName: string): string {
  return COUNTRY_TO_GEOJSON[ctName] ?? ctName
}

// ── Choropleth classification (the same engine for all three map modes) ──────
// Trial counts, disease prevalence and competition scores are all HIGHLY skewed:
// a handful of leaders sit far above a long tail. A linear colour ramp would let
// the single leader saturate to full colour and crush every other country into
// the palest shade — the classic choropleth failure. Instead we classify values
// into QUANTILE bins (each colour carries a roughly equal share of countries),
// draw them as discrete, single-hue steps, and label the numeric break points —
// the standard used by GBD, WHO and IQVIA maps. One shared engine keeps Density,
// Prevalence and Competition visually and behaviourally consistent.
const RAMPS: Record<MapMode, string[]> = {
  density:    ['#D2E4F2', '#A6C8E4', '#6BA3CE', '#2E77AE', '#005487'], // light blue → navy
  prevalence: ['#FDE4C6', '#FBC688', '#F5934A', '#E06A1E', '#C2410C'], // pale amber → burnt orange
  intensity:  ['#FCD9D9', '#F4A3A3', '#E86A6A', '#D62E2E', '#991B1B'], // pale rose → deep red
}
const NO_DATA_FILL = '#E8EEF3'
const MODE_META: Record<MapMode, { title: string; unit: string; hiLabel?: string; loLabel?: string }> = {
  density:    { title: 'Trial density (trials)',           unit: 'trials' },
  prevalence: { title: 'Disease prevalence (patients)',    unit: 'patients' },
  intensity:  { title: 'Recruitment competition',          unit: 'competing slots per 100k patients',
                hiLabel: 'crowded — hard to enrol', loLabel: 'open field' },
}

// k−1 quantile breakpoints from the positive values, de-duplicated so that data
// with many tied values simply yields fewer (but still valid) classes.
function quantileBreaks(values: number[], k: number): number[] {
  const v = values.filter(x => x > 0).sort((a, b) => a - b)
  if (v.length < 2) return []
  const raw: number[] = []
  for (let i = 1; i < k; i++) {
    const pos = (i / k) * (v.length - 1)
    const lo = Math.floor(pos), hi = Math.ceil(pos)
    raw.push(v[lo] + (v[hi] - v[lo]) * (pos - lo))
  }
  return [...new Set(raw.map(x => Math.round(x)))]
}
// class index 0..breaks.length for a value (0 = lowest bin)
function classOf(value: number, breaks: number[]): number {
  let i = 0
  while (i < breaks.length && value > breaks[i]) i++
  return i
}
// evenly-spread colour from the 5-stop ramp for class j of n total classes
function classColor(ramp: string[], j: number, n: number): string {
  if (n <= 1) return ramp[ramp.length - 1]
  return ramp[Math.round((j / (n - 1)) * (ramp.length - 1))]
}
// compact number formatter for legend labels (1.2k, 3.4M)
function fmtNum(n: number): string {
  if (n >= 1e6) return (n / 1e6).toFixed(n >= 1e7 ? 0 : 1).replace(/\.0$/, '') + 'M'
  if (n >= 1e3) return (n / 1e3).toFixed(n >= 1e4 ? 0 : 1).replace(/\.0$/, '') + 'k'
  return String(Math.round(n))
}

function siteIsRecruiting(status?: string): boolean {
  return (status ?? '').toUpperCase().includes('RECRUIT')
}

// Fly the map to fit a selected country's sites when the selection changes.
function FlyToSites({ sites }: { sites: Site[] }) {
  const map = useMap()
  useEffect(() => {
    if (!sites.length) return
    const lats = sites.map(s => s.lat)
    const lons = sites.map(s => s.lon)
    map.flyToBounds(
      [[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]],
      { padding: [50, 50], maxZoom: 6, duration: 0.8 }
    )
  }, [sites, map])
  return null
}

// When a site is picked from the list, fly to it and pop open its location card
// so the user can pinpoint any site without having to click a tiny dot.
function FocusMarker({ site, onOpen }: { site: Site | null; onOpen: (nctId: string) => void }) {
  const map = useMap()
  const ref = useRef<any>(null)
  useEffect(() => {
    if (!site) return
    map.flyTo([site.lat, site.lon], Math.max(map.getZoom(), 6), { duration: 0.8 })
    const t = setTimeout(() => ref.current?.openPopup(), 450)
    return () => clearTimeout(t)
  }, [site, map])
  if (!site) return null
  return (
    <CircleMarker ref={ref} center={[site.lat, site.lon]} radius={9}
      pathOptions={{ color: '#005487', fillColor: '#FE8A12', fillOpacity: 0.9, weight: 2 }}>
      <Popup>
        <div className="min-w-[160px]">
          <p className="text-xs font-semibold text-iq-navy leading-snug">{site.facility || 'Unnamed site'}</p>
          <div className="flex items-center gap-1 mt-1 text-[11px] text-iq-muted">
            <MapPin className="w-3 h-3 flex-shrink-0" />
            <span>{[site.city, site.country].filter(Boolean).join(', ')}</span>
          </div>
          <p className="text-[10px] text-iq-muted mt-0.5 font-mono">{site.lat.toFixed(3)}, {site.lon.toFixed(3)}</p>
          {site.status && (
            <p className={clsx('text-[11px] mt-1 font-medium', siteIsRecruiting(site.status) ? 'text-iq-green' : 'text-iq-muted')}>{site.status}</p>
          )}
          {site.nctId && (
            <button onClick={() => onOpen(site.nctId!)}
              className="mt-2 w-full text-[11px] font-medium text-iq-blue hover:text-iq-navy flex items-center justify-center gap-1 border border-iq-border rounded-md py-1 transition-colors">
              Open trial {site.nctId} <ExternalLink className="w-3 h-3" />
            </button>
          )}
        </div>
      </Popup>
    </CircleMarker>
  )
}

// Radius search: click the map to drop a search center; render the radius circle.
function RadiusPicker({ center, miles, active, onSet }: {
  center: [number, number] | null; miles: number; active: boolean; onSet: (c: [number, number]) => void
}) {
  useMapEvents({ click: (e) => { if (active) onSet([e.latlng.lat, e.latlng.lng]) } })
  if (!center) return null
  return (
    <Circle center={center} radius={miles * 1609.34}
      pathOptions={{ color: '#005487', fillColor: '#00A3E0', fillOpacity: 0.08, weight: 1.5 }} />
  )
}

function GeoLayer({ valueByGeo, colorFor, unit, mode, selectedGeo }: {
  valueByGeo: Record<string, number>; colorFor: (v: number) => string
  unit: string; mode: MapMode; selectedGeo: string | null
}) {
  const [geoJson, setGeoJson] = useState<GeoJSON.FeatureCollection | null>(null)
  const [loadFailed, setLoadFailed] = useState(false)
  const layerRef = useRef<any>(null)

  useEffect(() => {
    fetch(WORLD_GEOJSON_URL)
      .then(r => r.json())
      .then(setGeoJson)
      .catch(() => setLoadFailed(true))
  }, [])

  if (loadFailed) return null
  if (!geoJson) return null

  const styleFeature = (feature: any) => {
    const name = feature?.properties?.name ?? ''
    const value = valueByGeo[name] ?? 0
    const isSel = selectedGeo === name
    return {
      fillColor: colorFor(value),
      fillOpacity: 1,
      color: isSel ? '#005487' : '#D2DADF',
      weight: isSel ? 2 : 0.5,
    }
  }
  const bindFeature = (feature: any, layer: any) => {
    const name = feature.properties?.name ?? ''
    const value = valueByGeo[name] ?? 0
    const label = value > 0
      ? `${value.toLocaleString()} ${unit}`
      : (mode === 'prevalence' ? 'no prevalence data' : mode === 'intensity' ? 'no competition data' : '0 trials')
    layer.bindTooltip(
      `<div class="font-semibold text-xs">${name}</div>
       <div class="text-[10px] text-iq-muted mt-0.5">${label}</div>`,
      { sticky: true, className: 'leaflet-tooltip-iq' }
    )
  }

  // Draw the world minus its (inaccurate) India feature; the accurate India
  // outline is drawn as a second layer on top so it covers the disputed regions.
  const worldNoIndia: GeoJSON.FeatureCollection = {
    type: 'FeatureCollection',
    features: geoJson.features.filter((f) => f.properties?.name !== 'India'),
  }
  const sig = `${mode}:${selectedGeo ?? ''}:${Object.entries(valueByGeo).map(([k, v]) => k + v).join('')}`

  return (
    <>
      <GeoJSON
        ref={layerRef}
        key={`world:${sig}`}
        data={worldNoIndia}
        style={styleFeature}
        onEachFeature={bindFeature}
      />
      <GeoJSON
        key={`india:${sig}`}
        data={INDIA_OFFICIAL as GeoJSON.Feature}
        style={styleFeature}
        onEachFeature={bindFeature}
      />
    </>
  )
}

export function GeoPage() {
  const navigate = useNavigate()
  const { filters, setFilters } = useSharedSearch()
  const condition = filters.condition
  const [input, setInput] = useState(condition)
  const geoParams = filterParams(filters)

  const analyze = (c: string) => {
    const v = c.trim()
    if (v.length < 2) return
    setFilters({ condition: v })
  }
  const [view, setView] = useState<'map' | 'list'>('map')
  const [mapMode, setMapMode] = useState<MapMode>('density')
  const [whiteSpaceMode, setWhiteSpaceMode] = useState(false)
  const [selectedCountry, setSelectedCountry] = useState<string | null>(null)
  const [focusedSite, setFocusedSite] = useState<Site | null>(null)
  const [prevalenceInputs, setPrevalenceInputs] = useState<Record<string, string>>({})
  // Radius search (I): a clicked center + miles → filter.geo on the backend.
  const [radiusMode, setRadiusMode] = useState(false)
  const [radiusCenter, setRadiusCenter] = useState<[number, number] | null>(null)
  const [radiusMiles, setRadiusMiles] = useState(100)

  // Prevalence is needed for the White-Space panel, prevalence AND intensity modes.
  const { data: prevData } = useQuery({
    queryKey: ['prevalence', condition],
    queryFn: () => api.getPrevalence(condition),
    enabled: whiteSpaceMode || mapMode === 'prevalence' || mapMode === 'intensity',
  })

  const radiusParams = radiusMode && radiusCenter
    ? { geoLat: radiusCenter[0], geoLng: radiusCenter[1], geoMiles: radiusMiles }
    : {}
  const geoQuery = { ...geoParams, ...radiusParams }
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['geo', geoQuery],
    queryFn: () => api.getGeo(geoQuery),
  })

  const countries = data?.countries ?? []

  // Choropleth values keyed by GeoJSON polygon name.
  const densityByGeo: Record<string, number> = {}
  const intensityByGeo: Record<string, number> = {}
  countries.forEach(c => {
    const name = toGeoName(c.country)
    densityByGeo[name] = (densityByGeo[name] ?? 0) + c.trialCount
    if (c.competitionIntensity != null) intensityByGeo[name] = c.competitionIntensity
  })
  const prevalenceByGeo: Record<string, number> = {}
  Object.entries(prevData?.countries ?? {}).forEach(([ctName, v]) => {
    prevalenceByGeo[toGeoName(ctName)] = v.prevalence
  })

  const activeByGeo = mapMode === 'prevalence' ? prevalenceByGeo
    : mapMode === 'intensity' ? intensityByGeo : densityByGeo

  // Quantile classification — shared by the map fill and the legend so both are
  // always in lock-step. Handles the heavy skew of every mode automatically.
  const activeVals = Object.values(activeByGeo)
  const ramp = RAMPS[mapMode]
  const breaks = quantileBreaks(activeVals, 5)
  const nClasses = breaks.length + 1
  const positives = activeVals.filter(v => v > 0)
  const minVal = positives.length ? Math.min(...positives) : 0
  const maxVal = positives.length ? Math.max(...positives) : 1
  const colorFor = (v: number) => (v > 0 ? classColor(ramp, classOf(v, breaks), nClasses) : NO_DATA_FILL)
  // Legend rows, drawn high→low (darkest class on top), each with its value range.
  const legendRows = Array.from({ length: nClasses }, (_, j) => {
    const lo = j === 0 ? minVal : breaks[j - 1]
    const hi = j === nClasses - 1 ? maxVal : breaks[j]
    const label = lo === hi ? fmtNum(lo) : `${fmtNum(lo)}–${fmtNum(hi)}`
    return { color: classColor(ramp, j, nClasses), label }
  }).reverse()

  const unmappable = countries.filter(c => NO_POLYGON.has(c.country) && c.trialCount > 0)

  const selected = selectedCountry ? countries.find(c => c.country === selectedCountry) ?? null : null
  // Dots: all sites normally, or just the selected country's when drilled in.
  const shownSites = (selected ? selected.sites : countries.flatMap(c => c.sites)).slice(0, 300)
  const selectedGeo = selected ? toGeoName(selected.country) : null

  // Clear map drill-down state when the indication changes so a pinned site or
  // drilled country from the previous search doesn't linger on the new map.
  useEffect(() => {
    setSelectedCountry(null)
    setFocusedSite(null)
    setPrevalenceInputs({})
  }, [condition])

  const pickCountry = (name: string) => { setSelectedCountry(name); setView('map') }
  // Pin a site on the map (fly + open its card) instead of jumping to the trial.
  const pinSite = (s: Site) => { setView('map'); setFocusedSite(s) }

  return (
    <div className="flex flex-col h-full">
      <TopBar title="Geo Intelligence" subtitle="Global trial density · white-space opportunities · site mapping" />

      <div className="flex-1 overflow-hidden flex flex-col p-6 gap-4">
        {/* Controls */}
        <div className="flex gap-3 items-center flex-shrink-0 flex-wrap">
          <div className="flex-1 min-w-[240px] relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-iq-muted" />
            <input className="input-dark pl-9" value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && analyze(input)}
              placeholder="Indication for geo analysis…" />
          </div>
          <button onClick={() => analyze(input)} className="btn-primary">Map It</button>

          <div className="flex glass rounded-lg overflow-hidden border border-iq-border">
            {(['map', 'list'] as const).map(v => (
              <button key={v} onClick={() => setView(v)}
                className={clsx('px-3 py-2 text-xs font-medium flex items-center gap-1.5 transition-colors',
                  view === v ? 'bg-iq-blue/10 text-iq-navy' : 'text-iq-muted hover:text-iq-text')}>
                {v === 'map' ? <Map className="w-3.5 h-3.5" /> : <List className="w-3.5 h-3.5" />}
                {v === 'map' ? 'Map' : 'List'}
              </button>
            ))}
          </div>

          {/* Map layer mode */}
          <div className="flex glass rounded-lg overflow-hidden border border-iq-border">
            {([['density', 'Density', Activity], ['prevalence', 'Prevalence', Layers], ['intensity', 'Competition', Flame]] as const).map(([m, label, Icon]) => (
              <button key={m} onClick={() => setMapMode(m)}
                className={clsx('px-3 py-2 text-xs font-medium flex items-center gap-1.5 transition-colors',
                  mapMode === m ? 'bg-iq-blue/10 text-iq-navy' : 'text-iq-muted hover:text-iq-text')}>
                <Icon className="w-3.5 h-3.5" />
                {label}
              </button>
            ))}
          </div>

          <button onClick={() => { setRadiusMode(r => !r); if (radiusMode) setRadiusCenter(null) }}
            className={clsx('btn-ghost flex items-center gap-2 text-xs',
              radiusMode && 'bg-iq-blue/10 border-iq-blue/30 text-iq-navy')}>
            <Crosshair className="w-3.5 h-3.5" />
            Radius
          </button>

          <button onClick={() => setWhiteSpaceMode(w => !w)}
            className={clsx('btn-ghost flex items-center gap-2 text-xs',
              whiteSpaceMode && 'bg-iq-orange/10 border-iq-orange/30 text-iq-orange')}>
            <AlertCircle className="w-3.5 h-3.5" />
            White-Space
          </button>
        </div>

        {/* Radius search controls */}
        {radiusMode && (
          <div className="glass rounded-xl p-3 flex-shrink-0 flex items-center gap-3 flex-wrap border border-iq-blue/20">
            <span className="text-xs font-semibold text-iq-navy flex items-center gap-1.5"><Crosshair className="w-3.5 h-3.5 text-iq-blue" /> Radius Search</span>
            <span className="text-[11px] text-iq-muted">
              {radiusCenter ? `Center ${radiusCenter[0].toFixed(2)}, ${radiusCenter[1].toFixed(2)}` : 'Click anywhere on the map to set a center'}
            </span>
            <div className="flex items-center gap-1.5 ml-auto">
              {[50, 100, 250, 500].map(mi => (
                <button key={mi} onClick={() => setRadiusMiles(mi)}
                  className={clsx('chip text-[11px] px-2 py-0.5', radiusMiles === mi ? 'chip-active' : 'chip-idle')}>
                  {mi} mi
                </button>
              ))}
              {radiusCenter && (
                <button onClick={() => setRadiusCenter(null)} className="text-[11px] text-iq-muted hover:text-iq-navy ml-1">clear</button>
              )}
            </div>
            {radiusCenter && !isLoading && data && (
              <span className="w-full text-[11px] text-iq-blue font-medium">
                {data.coverage.total.toLocaleString()} trials with a site within {radiusMiles} mi of this point.
              </span>
            )}
          </div>
        )}

        {/* Upstream error */}
        {isError && (
          <div className="flex-shrink-0">
            <ErrorState compact error={error} onRetry={() => refetch()} />
          </div>
        )}

        <div className="flex-shrink-0"><ActiveFilters /></div>

        {/* Coverage disclosure */}
        {!isLoading && !isError && data && (
          <div className="flex-shrink-0 flex items-center gap-2">
            <CoverageBadge coverage={data.coverage} />
            {(mapMode === 'prevalence' || mapMode === 'intensity') && prevData?.modeled && (
              <span className="text-[10px] text-iq-muted flex items-center gap-1">
                <Cpu className="w-2.5 h-2.5 text-iq-blue" /> Modeled prevalence (epidemiology engine) — no AI key needed
              </span>
            )}
          </div>
        )}

        {/* Plain-language explainer for the Competition layer (it's the least
            self-evident of the three modes). */}
        {!isLoading && !isError && data && mapMode === 'intensity' && (
          <div className="flex-shrink-0 flex items-start gap-2 text-[11px] text-iq-muted bg-red-50/60 border border-red-100 rounded-lg px-3 py-2">
            <Flame className="w-3.5 h-3.5 text-red-500 flex-shrink-0 mt-0.5" />
            <p className="leading-snug">
              <span className="font-semibold text-iq-navy">How crowded each market is.</span> Counts the enrolment slots of
              every trial competing in a country, per 100,000 people who have this condition there.
              <span className="text-red-700 font-medium"> Darker = more competition</span> (many trials chasing the same
              patients — harder and slower to enrol); lighter = an open field.
              {!prevData?.found && <span className="text-iq-orange"> No prevalence data for this indication yet, so the map is empty — try a more common condition.</span>}
            </p>
          </div>
        )}

        {/* White-space panel */}
        {whiteSpaceMode && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
            className="glass rounded-xl p-4 flex-shrink-0 border border-iq-orange/20">
            <div className="flex items-start gap-3">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  {prevData?.modeled
                    ? <Cpu className="w-4 h-4 text-iq-blue flex-shrink-0" />
                    : <CheckCircle2 className="w-4 h-4 text-iq-green flex-shrink-0" />
                  }
                  <p className="text-xs font-semibold text-iq-navy">White-Space Opportunity Analysis</p>
                  {prevData?.modeled
                    ? <span className="text-[10px] bg-iq-blue/10 text-iq-navy border border-iq-blue/20 px-2 py-0.5 rounded-full flex items-center gap-1">
                        <Cpu className="w-2.5 h-2.5" /> Modeled estimate
                      </span>
                    : <span className="text-[10px] bg-green-50 text-green-700 border border-green-200 px-2 py-0.5 rounded-full flex items-center gap-1">
                        <Database className="w-2.5 h-2.5" /> Curated data
                      </span>
                  }
                </div>
                <p className="text-[11px] text-iq-muted mb-3">
                  {prevData?.note} Override any country below with your own numbers.
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {countries.slice(0, 8).map(c => {
                    const prefed = prevData?.countries?.[c.country]
                    const manualVal = prevalenceInputs[c.country]
                    const prevalence = manualVal ? parseInt(manualVal) : prefed?.prevalence
                    const wsScore = prevalence ? (prevalence / Math.max(c.siteCount * 1000, 1)).toFixed(1) : null

                    return (
                      <div key={c.country} className="bg-iq-bg rounded-lg p-2.5 border border-iq-border">
                        <p className="text-[11px] font-semibold text-iq-text mb-0.5 leading-snug" title={c.country}>{c.country}</p>
                        <p className="text-[9px] text-iq-muted mb-2">{c.trialCount} trials · {c.siteCount} sites</p>

                        {prefed && !manualVal && (
                          <p className="text-[10px] text-iq-green mb-1.5 font-mono">
                            {prefed.prevalence.toLocaleString()} pts
                          </p>
                        )}
                        <div className="flex items-center gap-1">
                          <Edit3 className="w-2.5 h-2.5 text-iq-muted flex-shrink-0" />
                          <input
                            className="w-full bg-iq-bg border border-iq-border rounded px-1.5 py-0.5 text-[10px] text-iq-text
                                       placeholder-iq-muted focus:outline-none focus:border-iq-orange/40"
                            placeholder={prefed ? 'Override…' : 'Prevalence (pts)'}
                            value={manualVal ?? ''}
                            onChange={e => setPrevalenceInputs(p => ({ ...p, [c.country]: e.target.value }))}
                          />
                        </div>
                        {wsScore && (
                          <div className="mt-1.5 flex items-center justify-between">
                            <span className="text-[9px] text-iq-muted">WS Score</span>
                            <span className={`text-[10px] font-bold ${parseFloat(wsScore) > 50 ? 'text-iq-green' : parseFloat(wsScore) > 10 ? 'text-iq-orange' : 'text-iq-muted'}`}>
                              {wsScore}x
                            </span>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* Map or List */}
        <div className="flex-1 min-h-0 flex gap-4">
          {view === 'map' ? (
            <div className="flex-1 glass rounded-xl overflow-hidden relative">
              {isLoading && (
                <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/80 rounded-xl">
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-8 h-8 border-2 border-iq-blue border-t-transparent rounded-full animate-spin" />
                    <p className="text-xs text-iq-muted">Loading geo data…</p>
                  </div>
                </div>
              )}
              <MapContainer
                center={[20, 0]} zoom={2} minZoom={2} maxZoom={8}
                style={{ height: '100%', width: '100%', background: '#E8EEF3' }}
                zoomControl={false}
              >
                <TileLayer
                  url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
                  subdomains="abcd"
                  maxZoom={20}
                />
                {!isLoading && <GeoLayer valueByGeo={activeByGeo} colorFor={colorFor} unit={MODE_META[mapMode].unit} mode={mapMode} selectedGeo={selectedGeo} />}
                <RadiusPicker center={radiusCenter} miles={radiusMiles} active={radiusMode} onSet={setRadiusCenter} />
                {selected && <FlyToSites sites={selected.sites} />}
                <FocusMarker site={focusedSite} onOpen={(id) => navigate(`/protocol/${id}`)} />
                {/* Dedicated pane ABOVE the choropleth (overlayPane z=400) so site
                    dots are never buried under a dark country fill. */}
                <Pane name="site-dots" style={{ zIndex: 640 }} />
                {shownSites.map((site, i) => {
                  const recruiting = siteIsRecruiting(site.status)
                  // Recruiting = green, other = deep magenta. Both are chosen to
                  // stay high-contrast on ANY choropleth (blue density, orange
                  // prevalence, red competition), and a bold white halo keeps
                  // every dot readable even where it overlaps a same-hue country.
                  const color = recruiting ? '#16A34A' : '#7C3AED'
                  return (
                    <CircleMarker
                      key={`${site.nctId ?? ''}-${site.lat}-${site.lon}-${i}`}
                      pane="site-dots"
                      center={[site.lat, site.lon]}
                      radius={selected ? 8 : 6}
                      pathOptions={{ color: '#FFFFFF', fillColor: color, fillOpacity: 1, weight: 2.5 }}
                    >
                      <LeafletTooltip>
                        <div className="text-xs font-semibold">{site.facility || site.city}</div>
                        <div className="text-[10px] text-iq-muted">{site.city}{site.city ? ', ' : ''}{site.country}</div>
                        {site.status && <div className="text-[10px] text-iq-blue">{site.status}</div>}
                      </LeafletTooltip>
                      {/* Click pins the site and shows its location details right here. */}
                      <Popup>
                        <div className="min-w-[160px]">
                          <p className="text-xs font-semibold text-iq-navy leading-snug">{site.facility || 'Unnamed site'}</p>
                          <div className="flex items-center gap-1 mt-1 text-[11px] text-iq-muted">
                            <MapPin className="w-3 h-3 flex-shrink-0" />
                            <span>{[site.city, site.country].filter(Boolean).join(', ')}</span>
                          </div>
                          <p className="text-[10px] text-iq-muted mt-0.5 font-mono">{site.lat.toFixed(3)}, {site.lon.toFixed(3)}</p>
                          {site.status && (
                            <p className={clsx('text-[11px] mt-1 font-medium', siteIsRecruiting(site.status) ? 'text-iq-green' : 'text-iq-muted')}>
                              {site.status}
                            </p>
                          )}
                          {site.nctId && (
                            <button
                              onClick={() => navigate(`/protocol/${site.nctId}`)}
                              className="mt-2 w-full text-[11px] font-medium text-iq-blue hover:text-iq-navy flex items-center justify-center gap-1 border border-iq-border rounded-md py-1 transition-colors"
                            >
                              Open trial {site.nctId} <ExternalLink className="w-3 h-3" />
                            </button>
                          )}
                        </div>
                      </Popup>
                    </CircleMarker>
                  )
                })}
              </MapContainer>

              {/* Legend */}
              <div className="absolute bottom-3 left-3 z-[400] glass rounded-lg px-3 py-2">
                <p className="text-[10px] font-semibold text-iq-navy mb-1.5">{MODE_META[mapMode].title}</p>
                {positives.length === 0 ? (
                  <p className="text-[9px] text-iq-muted">No data for this indication</p>
                ) : (
                  <div className="space-y-0.5">
                    {MODE_META[mapMode].hiLabel && (
                      <p className="text-[8px] text-red-600 font-medium leading-none mb-0.5">↑ {MODE_META[mapMode].hiLabel}</p>
                    )}
                    {legendRows.map((r, i) => (
                      <div key={i} className="flex items-center gap-1.5">
                        <span className="w-3 h-3 rounded-sm flex-shrink-0 border border-black/5" style={{ background: r.color }} />
                        <span className="text-[9px] text-iq-muted leading-none">{r.label}</span>
                      </div>
                    ))}
                    {MODE_META[mapMode].loLabel && (
                      <p className="text-[8px] text-iq-muted leading-none mt-0.5">↓ {MODE_META[mapMode].loLabel}</p>
                    )}
                    <div className="flex items-center gap-1.5 pt-0.5">
                      <span className="w-3 h-3 rounded-sm flex-shrink-0 border border-black/5" style={{ background: NO_DATA_FILL }} />
                      <span className="text-[9px] text-iq-muted leading-none">{mapMode === 'density' ? 'none' : 'no data'}</span>
                    </div>
                  </div>
                )}
                <div className="flex items-center gap-3 mt-1.5 pt-1.5 border-t border-iq-border">
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full ring-1 ring-white" style={{ background: '#16A34A' }} /><span className="text-[9px] text-iq-muted">Recruiting</span></span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full ring-1 ring-white" style={{ background: '#7C3AED' }} /><span className="text-[9px] text-iq-muted">Other</span></span>
                </div>
                <p className="text-[9px] text-iq-muted mt-1">showing {shownSites.length} sites</p>
                {!selected && unmappable.length > 0 && (
                  <p className="text-[9px] text-iq-muted mt-1 max-w-[140px] leading-snug">
                    {unmappable.map(c => c.country).join(', ')} shown as dots only (no region polygon)
                  </p>
                )}
              </div>

              {/* Selected-country banner */}
              {selected && (
                <div className="absolute top-3 left-3 z-[400] glass rounded-lg px-3 py-2 flex items-center gap-2">
                  <button onClick={() => setSelectedCountry(null)} className="text-iq-muted hover:text-iq-navy">
                    <ArrowLeft className="w-3.5 h-3.5" />
                  </button>
                  <div>
                    <p className="text-xs font-semibold text-iq-navy">{selected.country}</p>
                    <p className="text-[9px] text-iq-muted">{selected.trialCount} trials · {selected.siteCount} sites</p>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex-1 glass rounded-xl overflow-hidden flex flex-col">
              <div className="px-4 py-3 border-b border-iq-border flex items-center gap-3">
                <p className="text-sm font-semibold text-iq-navy">Country Rankings</p>
                <span className="text-xs text-iq-muted">{countries.length} countries · {condition}</span>
              </div>
              <div className="overflow-y-auto flex-1">
                {countries.map((c, i) => {
                  const pct = (c.trialCount / (countries[0]?.trialCount ?? 1)) * 100
                  const manualPrevalence = prevalenceInputs[c.country]
                  const prefedPrevalence = prevData?.countries?.[c.country]?.prevalence
                  const prevalence = manualPrevalence ? parseInt(manualPrevalence) : prefedPrevalence
                  const wsScore = prevalence ? (prevalence / Math.max(c.siteCount * 1000, 1)).toFixed(1) : null
                  return (
                    <div key={c.country} onClick={() => pickCountry(c.country)}
                      className="flex items-center gap-4 px-4 py-3 border-b border-iq-border hover:bg-iq-bg transition-colors cursor-pointer">
                      <span className="text-[11px] text-iq-muted w-5 text-right flex-shrink-0">{i + 1}</span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2 mb-1">
                          <span className="text-sm text-iq-text leading-snug" title={c.country}>{c.country}</span>
                          <span className="text-xs font-semibold text-iq-text flex-shrink-0 whitespace-nowrap">{c.trialCount} trials</span>
                        </div>
                        <div className="bg-iq-bg rounded-full h-1">
                          <div className="h-full rounded-full bg-gradient-to-r from-iq-blue to-iq-navy transition-all"
                            style={{ width: `${pct}%` }} />
                        </div>
                        <div className="flex items-center gap-3 mt-1">
                          <span className="text-[10px] text-iq-muted">{c.siteCount} sites</span>
                          {wsScore && <span className="text-[10px] text-iq-orange">WS Score: {wsScore}x</span>}
                        </div>
                      </div>
                      <ChevronRight className="w-3.5 h-3.5 text-iq-muted flex-shrink-0" />
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Right sidebar — Top Markets, or site details when a country is selected */}
          <div className="w-64 flex-shrink-0 glass rounded-xl overflow-hidden flex flex-col">
            {selected ? (
              <>
                <div className="px-3 py-3 border-b border-iq-border flex items-center gap-2">
                  <button onClick={() => setSelectedCountry(null)} className="text-iq-muted hover:text-iq-navy">
                    <ArrowLeft className="w-3.5 h-3.5" />
                  </button>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-iq-navy truncate">{selected.country}</p>
                    <p className="text-[10px] text-iq-muted">{selected.sites.length} sites shown</p>
                  </div>
                </div>
                <div className="overflow-y-auto flex-1">
                  {selected.sites.length === 0 && (
                    <p className="px-3 py-4 text-[11px] text-iq-muted">No geo-located sites for this country in the analyzed sample.</p>
                  )}
                  {selected.sites.map((s, i) => (
                    <div key={`${s.nctId}-${i}`}
                      onClick={() => pinSite(s)}
                      className="px-3 py-2.5 border-b border-iq-border transition-colors hover:bg-iq-bg cursor-pointer group">
                      <div className="flex items-start gap-1.5">
                        <Building2 className="w-3 h-3 text-iq-muted flex-shrink-0 mt-0.5" />
                        <p className="text-[11px] text-iq-text leading-snug line-clamp-2 flex-1">{s.facility || 'Unnamed site'}</p>
                      </div>
                      <div className="flex items-center gap-1.5 mt-1 pl-4">
                        <MapPin className="w-2.5 h-2.5 text-iq-muted flex-shrink-0" />
                        <span className="text-[10px] text-iq-muted truncate">{s.city || '—'}</span>
                      </div>
                      <div className="flex items-center justify-between mt-1 pl-4">
                        {s.status
                          ? <span className={clsx('text-[9px] font-medium', siteIsRecruiting(s.status) ? 'text-iq-green' : 'text-iq-muted')}>{s.status}</span>
                          : <span className="text-[9px] text-iq-muted">status n/a</span>}
                        <span className="text-[9px] text-iq-blue flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                          Locate on map <MapPin className="w-2.5 h-2.5" />
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <>
                <div className="px-3 py-3 border-b border-iq-border">
                  <p className="text-xs font-semibold text-iq-navy">Top Markets</p>
                  <p className="text-[9px] text-iq-muted mt-0.5">click a country to drill in</p>
                </div>
                <div className="overflow-y-auto flex-1">
                  {isLoading
                    ? Array.from({ length: 6 }).map((_, i) => (
                        <div key={i} className="px-3 py-2.5 border-b border-iq-border">
                          <div className="h-2.5 bg-iq-bg rounded animate-pulse mb-1" />
                          <div className="h-2 bg-iq-bg rounded animate-pulse w-2/3" />
                        </div>
                      ))
                    : countries.slice(0, 20).map((c) => (
                        <div key={c.country} onClick={() => pickCountry(c.country)}
                          className="px-3 py-2.5 border-b border-iq-border hover:bg-iq-bg transition-colors cursor-pointer group">
                          <div className="flex items-start justify-between gap-2">
                            <span className="text-xs text-iq-text leading-snug flex-1 min-w-0" title={c.country}>{c.country}</span>
                            <span className="text-[11px] font-bold text-iq-blue flex-shrink-0">{c.trialCount}</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <p className="text-[10px] text-iq-muted">{c.siteCount} sites</p>
                            <ChevronRight className="w-3 h-3 text-iq-border group-hover:text-iq-blue transition-colors" />
                          </div>
                        </div>
                      ))
                  }
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
