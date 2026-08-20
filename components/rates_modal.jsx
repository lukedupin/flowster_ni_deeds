import React, { Fragment, useEffect, useState } from 'react'
import { Dialog, Transition } from '@headlessui/react'
import * as Util from "../../src/helpers/util.js"
import { WEB_URL } from "../../src/settings"

export const RatesModal = props => {
    const { open, showToast } = props
    const onClose = props.onClose || (() => {})

    const [rates, setRates] = useState([])

    useEffect(() => {
        if ( !open ) {
            return
        }

        Util.fetch_js(`${WEB_URL}/api/ni_deeds/rates`, null,
            js => setRates(js.rates),
            err => showToast?.(err, "error"))
    }, [open])

    return (
        <Transition.Root show={open} as={Fragment}>
            <Dialog as="div" className="relative z-50" onClose={onClose}>
                <Transition.Child
                    as={Fragment}
                    enter="ease-out duration-300"
                    enterFrom="opacity-0"
                    enterTo="opacity-100"
                    leave="ease-in duration-200"
                    leaveFrom="opacity-100"
                    leaveTo="opacity-0">
                    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" />
                </Transition.Child>

                <div className="fixed inset-0 z-50 w-screen overflow-y-auto">
                    <div className="flex min-h-full items-center justify-center p-4 text-center">
                        <Transition.Child
                            as={Fragment}
                            enter="ease-out duration-300"
                            enterFrom="opacity-0 translate-y-4 sm:scale-95"
                            enterTo="opacity-100 translate-y-0 sm:scale-100"
                            leave="ease-in duration-200"
                            leaveFrom="opacity-100 translate-y-0 sm:scale-100"
                            leaveTo="opacity-0 translate-y-4 sm:scale-95"
                        >
                            <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-white px-4 pb-4 pt-5 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-xs sm:p-6">
                                <Dialog.Title as="h3" className="text-base font-semibold leading-6 text-gray-900">
                                    30yr Mortgage Rates
                                </Dialog.Title>
                                <div className="mt-3 max-h-[60vh] overflow-y-auto">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr>
                                                <th className="pb-1 pr-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                                                <th className="pb-1 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Rate</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-gray-100">
                                            {[...rates].reverse().map(r => (
                                                <tr key={r.date}>
                                                    <td className="py-1 pr-4 text-gray-500">{r.date}</td>
                                                    <td className="py-1 text-right text-gray-900">{r.rate}%</td>
                                                </tr>
                                            ))}
                                            {rates.length === 0 && (
                                                <tr>
                                                    <td className="py-4 text-center text-gray-400">Loading...</td>
                                                </tr>
                                            )}
                                        </tbody>
                                    </table>
                                </div>
                                <div className="mt-4 sm:flex sm:flex-row-reverse">
                                    <button
                                        type="button"
                                        className="inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 sm:w-auto"
                                        onClick={onClose}>
                                        Close
                                    </button>
                                </div>
                            </Dialog.Panel>
                        </Transition.Child>
                    </div>
                </div>
            </Dialog>
        </Transition.Root>
    )
}
