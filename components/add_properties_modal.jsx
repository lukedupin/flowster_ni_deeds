import React, { Fragment, useEffect, useRef, useState } from 'react'
import { Dialog, Transition } from '@headlessui/react'
import { PlusIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { Spinner } from "../../src/components/spinner"
import * as Util from "../../src/helpers/util.js"
import { WEB_URL } from "../../src/settings"

const stripBullet = line => line.replace(/^\s*(?:[-*•]|\d+[.)])\s*/, '').trim()

export const AddPropertiesModal = props => {
    const { open, onClose, showToast } = props
    const onBegin = props.onBegin || (() => {})

    const [text, setText] = useState('')
    const [sanitizing, setSanitizing] = useState(false)

    const textareaRef = useRef(null)

    useEffect(() => {
        if ( !open ) {
            setText('')
            setSanitizing(false)
        }
    }, [open])

    const handleSanitize = () => {
        setSanitizing(true)
        Util.post_js(`${WEB_URL}/api/ni_deeds/clean_addresses`, {prompt: text},
            js => {
                setSanitizing(false)
                setText(js.addresses)
            },
            err => {
                setSanitizing(false)
                showToast?.(err, "error")
            })
    }

    const handleBegin = () => {
        const addresses = text.split('\n').map(stripBullet).filter(line => line.length > 0)
        if ( addresses.length === 0 ) {
            showToast?.("Please enter at least one address", "warning")
            return
        }

        onBegin(addresses)
        onClose()
    }

    return (
        <Transition.Root show={open} as={Fragment}>
            <Dialog as="div" className="relative z-40" onClose={onClose} initialFocus={textareaRef}>
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
                                <div className="absolute right-0 top-0 hidden pr-4 pt-4 sm:block">
                                    <button
                                        type="button"
                                        className="rounded-md bg-white text-gray-400 hover:text-gray-500 focus:outline-none"
                                        onClick={onClose}>
                                        <span className="sr-only">Close</span>
                                        <XMarkIcon className="h-6 w-6" aria-hidden="true" />
                                    </button>
                                </div>
                                <div className="sm:flex sm:items-start">
                                    <div
                                        className="mx-auto flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-blue-500 sm:mx-0 sm:h-10 sm:w-10">
                                        <PlusIcon className="h-6 w-6 text-white flex-shrink-0" aria-hidden="true" />
                                    </div>
                                    <div className="mt-3 text-center sm:mx-4 sm:mt-0 sm:text-left w-full">
                                        <Dialog.Title as="h3" className="text-base font-semibold leading-6 text-gray-900">
                                            Add Properties
                                        </Dialog.Title>
                                        <p className="mt-1 text-sm text-gray-500">
                                            Drop addresses into the textarea below, one address per line.
                                        </p>
                                        <div className="mt-3 w-full">
                                            <textarea
                                                ref={textareaRef}
                                                rows={10}
                                                disabled={sanitizing}
                                                className="block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-blue-600 sm:text-sm sm:leading-6"
                                                placeholder={"123 Main St\n456 Elm St"}
                                                value={text}
                                                onChange={e => setText(e.target.value)}
                                            />
                                        </div>
                                    </div>
                                </div>
                                <div className="mt-5 sm:mt-4 sm:flex sm:items-center sm:justify-between">
                                    <button
                                        type="button"
                                        disabled={sanitizing}
                                        className="mt-3 inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 disabled:opacity-50 sm:mt-0 sm:w-auto"
                                        onClick={onClose}>
                                        Cancel
                                    </button>
                                    <div className="sm:flex sm:flex-row-reverse">
                                        <button
                                            type="button"
                                            disabled={sanitizing}
                                            className="inline-flex w-full justify-center items-center rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 disabled:opacity-50 sm:ml-3 sm:w-auto"
                                            onClick={handleBegin}>
                                            Begin
                                        </button>
                                        <button
                                            type="button"
                                            disabled={sanitizing}
                                            className="mt-3 inline-flex w-full justify-center items-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 disabled:opacity-50 sm:mt-0 sm:w-auto"
                                            onClick={handleSanitize}>
                                            {sanitizing && <Spinner className="mr-2 h-4 w-4 text-gray-500" />}
                                            Sanitize
                                        </button>
                                    </div>
                                </div>
                            </Dialog.Panel>
                        </Transition.Child>
                    </div>
                </div>
            </Dialog>
        </Transition.Root>
    )
}
