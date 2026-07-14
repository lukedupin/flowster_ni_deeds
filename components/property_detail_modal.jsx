import React, { Fragment, useEffect, useState } from 'react'
import { Dialog, Transition } from '@headlessui/react'
import { DocumentTextIcon, HomeModernIcon, TrashIcon } from '@heroicons/react/24/outline'
import { Spinner } from "../../src/components/spinner"
import { MarkdownViewer } from "../../src/components/markdown_viewer.jsx"
import { ConfirmModal } from "../../src/modals/confirm_modal.jsx"
import * as Util from "../../src/helpers/util.js"
import { WEB_URL } from "../../src/settings"

const EXCLUDED_CONTENT_KEYS = ['owner', 'address', 'loan_amount', 'riders']

const formatValue = value => {
    if ( value === null || value === undefined || value === '' ) {
        return '-'
    }
    if ( Array.isArray(value) ) {
        return value.length > 0 ? value.join(', ') : '-'
    }
    if ( typeof value === 'object' ) {
        return JSON.stringify(value)
    }
    return String(value)
}

const humanizeKey = key => key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())

const buildMarkdown = property => {
    const content = property.content || {}
    const remaining = Object.entries(content).filter(([key]) => !EXCLUDED_CONTENT_KEYS.includes(key))
    const detailItems = remaining
        .map(([key, value]) => `* **${humanizeKey(key)}** ${formatValue(value)}`)
        .join('\n')
    const createdOn = property.timestamp_on ? new Date(property.timestamp_on).toLocaleDateString() : '-'

    return `## ${formatValue(property.initial_address)}

**${formatValue(property.found_name)}**

**Amount:** ${formatValue(content.loan_amount)}

**Riders:** ${formatValue(content.riders)}

**Created On:** ${createdOn}
${remaining.length > 0 ? `\n### Details\n\n${detailItems}` : ''}
`
}

export const PropertyDetailModal = props => {
    const { open, property, onClose, showToast } = props
    const onDeleted = props.onDeleted || (() => {})
    const onUpdate = props.onUpdate || (() => {})

    const [deleting, setDeleting] = useState(false)
    const [confirmingDelete, setConfirmingDelete] = useState(false)
    const [notes, setNotes] = useState('')

    useEffect(() => {
        setNotes(property?.notes || '')
    }, [property])

    const handleViewDeed = () => {
        window.open(`${WEB_URL}/api/ni_deeds/property/${property.uid}/pdf`, '_blank')
    }

    const handleDelete = () => {
        setConfirmingDelete(false)
        setDeleting(true)
        Util.post_js(`${WEB_URL}/api/ni_deeds/property/${property.uid}/delete`, {},
            () => {
                setDeleting(false)
                onDeleted()
            },
            err => {
                setDeleting(false)
                showToast?.(err, "error")
            })
    }

    const handleNotesBlur = () => {
        if ( notes === (property?.notes || '') ) {
            return
        }

        Util.post_js(`${WEB_URL}/api/ni_deeds/property/${property.uid}/notes`, {notes},
            () => onUpdate({ ...property, notes }),
            err => showToast?.(err, "error"))
    }

    return (
        <Fragment>
        <Transition.Root show={open} as={Fragment}>
            <Dialog as="div" className="relative z-40" onClose={onClose}>
                <Transition.Child
                    as={Fragment}
                    enter="ease-out duration-300"
                    enterFrom="opacity-0"
                    enterTo="opacity-100"
                    leave="ease-in duration-200"
                    leaveFrom="opacity-100"
                    leaveTo="opacity-0"
                >
                    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" />
                </Transition.Child>

                <div className="fixed inset-0 z-40 w-screen overflow-y-auto">
                    <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
                        <Transition.Child
                            as={Fragment}
                            enter="ease-out duration-300"
                            enterFrom="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
                            enterTo="opacity-100 translate-y-0 sm:scale-100"
                            leave="ease-in duration-200"
                            leaveFrom="opacity-100 translate-y-0 sm:scale-100"
                            leaveTo="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
                        >
                            <Dialog.Panel
                                className="relative transform overflow-hidden rounded-lg bg-white px-4 pb-4 pt-5 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg sm:p-6">
                                {property && (
                                    <>
                                        <div className="flex items-center justify-between">
                                            <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-blue-500">
                                                <HomeModernIcon className="h-6 w-6 text-white" aria-hidden="true" />
                                            </div>

                                            <button
                                                type="button"
                                                onClick={handleViewDeed}
                                                className="inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-800"
                                            >
                                                <DocumentTextIcon className="h-5 w-5" />
                                                View Deed
                                            </button>
                                        </div>

                                        <div className="mt-3 text-left w-full">
                                            {property.processing_log && (
                                                <div className="mb-3">
                                                    <h4 className="text-sm font-semibold text-red-600">Processing Error</h4>
                                                    <p className="mt-1 text-sm text-red-600">{property.processing_log}</p>
                                                </div>
                                            )}

                                            <div className="max-h-[60vh] overflow-y-auto">
                                                <MarkdownViewer content={buildMarkdown(property)} showToast={showToast} />
                                            </div>

                                            <textarea
                                                rows={4}
                                                value={notes}
                                                onChange={e => setNotes(e.target.value)}
                                                onBlur={handleNotesBlur}
                                                placeholder="Notes..."
                                                className="mt-4 block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-blue-600 sm:text-sm sm:leading-6"
                                            />
                                        </div>

                                        <div className="mt-5 sm:mt-4 flex items-center justify-between">
                                            <button
                                                type="button"
                                                disabled={deleting}
                                                className="inline-flex items-center gap-1.5 rounded-md bg-red-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-500 disabled:opacity-50"
                                                onClick={() => setConfirmingDelete(true)}>
                                                {deleting && <Spinner className="h-4 w-4 text-white" />}
                                                <TrashIcon className="h-4 w-4" />
                                                Delete
                                            </button>
                                            <button
                                                type="button"
                                                className="inline-flex justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
                                                onClick={onClose}>
                                                Close
                                            </button>
                                        </div>
                                    </>
                                )}
                            </Dialog.Panel>
                        </Transition.Child>
                    </div>
                </div>
            </Dialog>
        </Transition.Root>

        {property && (
            <ConfirmModal
                open={confirmingDelete}
                danger={true}
                title="Delete Property?"
                message={`Are you sure you want to delete ${property.initial_address}? This cannot be undone.`}
                confirmBtn="Delete"
                onClose={() => setConfirmingDelete(false)}
                onConfirm={handleDelete}
            />
        )}
        </Fragment>
    )
}
