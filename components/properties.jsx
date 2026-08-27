import React, { useEffect, useState } from 'react'
import { ArrowTopRightOnSquareIcon, DocumentTextIcon } from "@heroicons/react/24/outline"
import * as Util from "../../src/helpers/util.js"
import { WEB_URL } from "../../src/settings"
import { Sortable } from "../../src/components/sortable.jsx"
import { PropertyDetailModal } from "./property_detail_modal.jsx"
import { RatesModal } from "./rates_modal.jsx"

const COLUMNS = [
    { key: 'found_name', label: 'Owner Name' },
    { key: 'initial_address', label: 'Address' },
    { key: 'amount', label: 'Amount' },
    { key: 'riders', label: 'Riders' },
    { key: 'est_rate', label: 'Est Rate' },
    { key: 'timestamp_on', label: 'Created On' },
]

const formatRiders = riders => {
    if ( Array.isArray(riders) ) {
        return riders.join(', ')
    }
    return riders || ''
}

const formatRate = rate => (rate || rate === 0) ? `${rate}%` : ''

const sortValue = (property, key) => {
    switch ( key ) {
        case 'amount':
            return property.content?.loan_amount || ''
        case 'riders':
            return formatRiders(property.content?.riders)
        case 'est_rate':
            return property.content?.est_rate ?? ''
        default:
            return property[key] || ''
    }
}

const searchValue = (property, key) => {
    if ( key === 'timestamp_on' ) {
        return property.timestamp_on ? new Date(property.timestamp_on).toLocaleDateString() : ''
    }
    return sortValue(property, key)
}

const matchesSearch = (property, search) => {
    const search_lower = Util.xstr(search).trim().toLowerCase()
    if ( !search_lower ) {
        return true
    }

    return COLUMNS.some(col => Util.xstr(searchValue(property, col.key)).toLowerCase().includes(search_lower))
}

export const Properties = React.forwardRef((props, ref) => {
    const {search, showToast } = props
    const [properties, setProperties] = useState([])
    const [sort, setSort] = useState({ key: 'initial_address', asc: true })
    const [selected, setSelected] = useState(null)
    const [highlightedUid, setHighlightedUid] = useState(null)
    const [newUids, setNewUids] = useState(new Set())
    const [ratesOpen, setRatesOpen] = useState(false)

    const handleOpenRates = e => {
        e.stopPropagation()
        setRatesOpen(true)
    }

    const loadProperties = () => {
        const wasHere = new Set(properties.map(p => p.uid))
        Util.post_js(`${WEB_URL}/api/ni_deeds/properties`, null,
            js => {
                setProperties(js.properties)
                setNewUids(new Set(js.properties.filter(p => !wasHere.has(p.uid)).map(p => p.uid)))
            },
            err => showToast?.(err, "error"))
    }

    React.useImperativeHandle(ref, () => ({
        refresh: loadProperties,
    }))

    useEffect(() => {
        loadProperties()
    }, [])

    const handleSort = key => {
        setSort(prev => ({ key, asc: prev.key === key ? !prev.asc : true }))
    }

    const handleViewPdf = (e, uid) => {
        e.stopPropagation()
        setHighlightedUid(uid)
        window.open(`${WEB_URL}/api/ni_deeds/property/${uid}/pdf`, '_blank')
    }

    const handleDeleted = () => {
        setSelected(null)
        loadProperties()
    }

    const handlePropertyUpdate = updated => {
        setProperties(prev => prev.map(p => p.uid === updated.uid ? updated : p))
        setSelected(updated)
    }

    const filtered = properties.filter(property => matchesSearch(property, search))

    const sorted = [...filtered].sort((a, b) => {
        const av = sortValue(a, sort.key)
        const bv = sortValue(b, sort.key)
        if ( av < bv ) return sort.asc ? -1 : 1
        if ( av > bv ) return sort.asc ? 1 : -1
        return 0
    })

    return (
        <div className="w-full flex-1 overflow-auto p-4">
            <table className="w-full divide-y divide-gray-200 bg-white shadow rounded-lg">
                <thead className="bg-gray-50">
                    <tr>
                        {COLUMNS.map(col => (
                            <th
                                key={col.key}
                                onClick={() => handleSort(col.key)}
                                className="group px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer select-none"
                            >
                                <span className="inline-flex items-center">
                                    {col.label}
                                    <Sortable show={sort.key === col.key} asc={sort.asc} />
                                    {col.key === 'est_rate' && (
                                        <ArrowTopRightOnSquareIcon
                                            className="ml-1 h-3.5 w-3.5 text-gray-400 hover:text-blue-600"
                                            onClick={handleOpenRates}
                                        />
                                    )}
                                </span>
                            </th>
                        ))}
                        <th className="px-4 py-3" />
                    </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                    {sorted.map(property => (
                        <tr
                            key={property.uid}
                            onClick={() => setHighlightedUid(property.uid)}
                            className={`hover:bg-gray-50 ${highlightedUid === property.uid ? 'bg-blue-50' : newUids.has(property.uid) ? 'bg-amber-50' : ''}`}
                        >
                            <td
                                className="cursor-pointer px-4 py-3 text-sm text-gray-900 hover:underline"
                                onClick={() => setSelected(property)}
                            >
                                {property.found_name || '-'}
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-900">{property.content?.address || property.initial_address}</td>
                            <td className="px-4 py-3 text-sm text-gray-900">{property.content?.loan_amount || '-'}</td>
                            <td className="px-4 py-3 text-sm text-gray-900">{formatRiders(property.content?.riders) || '-'}</td>
                            <td className="px-4 py-3 text-sm text-gray-900">{formatRate(property.content?.est_rate) || '-'}</td>
                            <td
                                className="cursor-pointer px-4 py-3 text-sm text-gray-900 hover:underline"
                                onClick={() => setSelected(property)}
                            >
                                {property.timestamp_on ? new Date(property.timestamp_on).toLocaleDateString() : '-'}
                            </td>
                            <td className="px-4 py-3 text-right">
                                <button onClick={e => handleViewPdf(e, property.uid)} title="View PDF">
                                    <DocumentTextIcon className="h-5 w-5 text-gray-500 hover:text-blue-600" />
                                </button>
                            </td>
                        </tr>
                    ))}
                    {sorted.length === 0 && (
                        <tr>
                            <td colSpan={COLUMNS.length + 1} className="px-4 py-6 text-center text-sm text-gray-400">
                                No properties found.
                            </td>
                        </tr>
                    )}
                </tbody>
            </table>

            <PropertyDetailModal
                open={!!selected}
                property={selected}
                onClose={() => setSelected(null)}
                onDeleted={handleDeleted}
                onUpdate={handlePropertyUpdate}
                showToast={showToast}
            />

            <RatesModal
                open={ratesOpen}
                onClose={() => setRatesOpen(false)}
                showToast={showToast}
            />
        </div>
    )
})
