import React, {useState, useRef, useEffect, forwardRef} from 'react'
import {
    Send,
    Paperclip,
    Mic,
    EditIcon,
    PlusIcon,
    BrainIcon,
    PlusCircleIcon, DownloadIcon,
    ScrollText
} from 'lucide-react'
import * as Util from "../src/helpers/util.js"
import { marked } from 'marked';
//import 'github-markdown-css/github-markdown.css';
import 'github-markdown-css/github-markdown-light.css';
import { XMarkIcon } from "@heroicons/react/20/solid";
import {
    BarsArrowDownIcon,
    CheckCircleIcon
} from "@heroicons/react/24/outline/index";
import { Microphone } from "../src/components/microphone.jsx";
import {WEB_URL, WS_URL} from "../src/settings";
import { ChatTextArea } from "../src/components/chat_text_area.jsx";
import {
    MarkdownViewer,
    saveAsMarkdown
} from "../src/components/markdown_viewer.jsx";
import {Conversation} from "../src/components/conversation.jsx";
import {ChatContext} from "../src/components/ChatContext.jsx";
//import {COMMITS, GraphSVG} from "../../src/components/git_graph.jsx";
const wsUrl = `${WS_URL}/api/speech_to_text`;


export const Deeds = props => {
    const {showToast} = props
    const [scrollLock, setScrollLock] = useState(false)
    const [contextCount, setContextCount] = useState(0)

    const messagesEndRef = useRef(null)
    const chatTextAreaRef = useRef(null)
    const conversationRef = useRef(null)
    const chatContextRef = useRef(null)

    const handleMessageChange = () => {
        if ( scrollLock ) {
            messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
        }
    }

    const prevScrollYRef = useRef(0);
    useEffect(() => {
        //if (!scrollLock) {
            //return
        //}

        const onScroll = () => {
            const currentScrollY = window.scrollY ?? window.pageYOffset;
            const prevScrollY   = prevScrollYRef.current;

            if (currentScrollY > prevScrollY) {
                //
            } else if (currentScrollY < prevScrollY) {
                setScrollLock(false)
            }

            prevScrollYRef.current = currentScrollY;
        };

        window.addEventListener('scroll', onScroll, { passive: true });

        return () => window.removeEventListener('scroll', onScroll);
    }, [])

    const handleCreateAgent = () => {
        Util.post_js('/api/agent_create', {contexts: chatContextRef.current?.getContexts(true) ?? []},
            js => showToast("Agent created successfully! " + js.agent_uid, "success"),
            err => showToast(err))
    }

    const handleFullRetry = (content) => {
        conversationRef.current.handleRetry(content)
    }

    const handleLocalRetry = (content) => {
        chatTextAreaRef.current.setMessage(content)
    }

    const handleSend = (message, model) => {
        setScrollLock(true)
        conversationRef.current.handleSend(message, model, chatContextRef.current?.getContexts(true) ?? [])
    }

    return (
        <div className="relative flex-1 flex flex-col h-full bg-gray-50">
            {scrollLock && (
                <button
                    onClick={() => setScrollLock(false)}
                    className="fixed top-20 right-4 z-50 rounded-full bg-blue-500 shadow-md p-2 text-white hover:bg-blue-600 transition-colors"
                >
                    <ScrollText className="w-5 h-5" />
                </button>
            )}
            {/*}
            <div className="flex inline-flex">
                <div className="w-min">
                    <GraphSVG
                        className="w-6 h-6 text-blue-500 inline-block mr-2"
                        commits={COMMITS}
                        activeBranch={null}
                    />
                </div>
                <div className="w-full">
                {*/}
            <Conversation
                ref={conversationRef}
                onMessageChange={handleMessageChange}
                onRetry={handleLocalRetry}
                onStreamEnd={() => setScrollLock(false)}
                onUpdateContext={(name, content) => chatContextRef.current?.handleUpdateContext(name, content)}
                showToast={showToast}
            />

            <div ref={messagesEndRef} />

            <ChatContext 
                ref={chatContextRef} 
                onContextChanged={setContextCount}
                showToast={showToast} 
                />

            <ChatTextArea
                ref={chatTextAreaRef}
                className={'border-t'}
                context_count={contextCount}
                onSend={handleSend}
                onAttachment={() => chatContextRef.current?.handleAttachment()}
                onCreateAgent={handleCreateAgent}
                onRetry={handleFullRetry}
                showToast={showToast}
            />
        </div>
    )
}
