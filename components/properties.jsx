import React, { useEffect, useState } from 'react'
import { DocumentTextIcon } from "@heroicons/react/24/outline"
import * as Util from "../../src/helpers/util.js"
import { WEB_URL } from "../../src/settings"
import { Sortable } from "../../src/components/sortable.jsx"

const COLUMNS = [
    { key: 'found_name', label: 'Owner Name' },
    { key: 'initial_address', label: 'Address' },
    { key: 'amount', label: 'Amount' },
    { key: 'riders', label: 'Riders' },
    { key: 'timestamp_on', label: 'Created On' },
]

const sortValue = (property, key) => {
    switch ( key ) {
        case 'amount':
            return property.content?.loan_amount || ''
        case 'riders':
            return (property.content?.riders || []).join(', ')
        default:
            return property[key] || ''
    }
}

export const Properties = React.forwardRef((props, ref) => {
    const {search, showToast } = props
    const [properties, setProperties] = useState([])
    const [sort, setSort] = useState({ key: 'initial_address', asc: true })

    const loadProperties = () => {
        Util.post_js(`${WEB_URL}/api/ni_deeds/properties`, null,
            js => setProperties(js.properties),
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

    const handleViewPdf = uid => {
        window.open(`${WEB_URL}/api/ni_deeds/property/${uid}/pdf`, '_blank')
    }

    const sorted = [...properties].sort((a, b) => {
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
                                </span>
                            </th>
                        ))}
                        <th className="px-4 py-3" />
                    </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                    {sorted.map(property => (
                        <tr key={property.uid} className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm text-gray-900">{property.found_name || '-'}</td>
                            <td className="px-4 py-3 text-sm text-gray-900">{property.initial_address}</td>
                            <td className="px-4 py-3 text-sm text-gray-900">{property.content?.loan_amount || '-'}</td>
                            <td className="px-4 py-3 text-sm text-gray-900">{(property.content?.riders || []).join(', ') || '-'}</td>
                            <td className="px-4 py-3 text-sm text-gray-900">
                                {property.timestamp_on ? new Date(property.timestamp_on).toLocaleDateString() : '-'}
                            </td>
                            <td className="px-4 py-3 text-right">
                                <button onClick={() => handleViewPdf(property.uid)} title="View PDF">
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
        </div>
    )
})
