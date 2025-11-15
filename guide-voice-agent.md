# Build a Voice Agent

GET /v1/agent/converse

Build a conversational voice agent using Deepgram's Voice Agent WebSocket

## AsyncAPI Specification

```yaml
asyncapi: 2.6.0
info:
  title: agent.v1
  version: subpackage_agent/v1.agent.v1
  description: Build a conversational voice agent using Deepgram's Voice Agent WebSocket
channels:
  /v1/agent/converse:
    description: Build a conversational voice agent using Deepgram's Voice Agent WebSocket
    bindings:
      ws:
        headers:
          type: object
          properties:
            Authorization:
              type: string
    publish:
      operationId: agent-v-1-publish
      summary: Server messages
      message:
        oneOf:
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-server-0-AgentV1ReceiveFunctionCallResponse
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-server-1-AgentV1PromptUpdated
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-server-2-AgentV1SpeakUpdated
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-server-3-AgentV1InjectionRefused
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-server-4-AgentV1Welcome
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-server-5-AgentV1SettingsApplied
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-server-6-AgentV1ConversationText
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-server-7-AgentV1UserStartedSpeaking
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-server-8-AgentV1AgentThinking
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-server-9-AgentV1FunctionCallRequest
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-server-10-AgentV1AgentStartedSpeaking
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-server-11-AgentV1AgentAudioDone
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-server-12-AgentV1Error
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-server-13-AgentV1Warning
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-server-14-AgentV1Audio
    subscribe:
      operationId: agent-v-1-subscribe
      summary: Client messages
      message:
        oneOf:
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-client-0-AgentV1Settings
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-client-1-AgentV1UpdateSpeak
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-client-2-AgentV1InjectUserMessage
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-client-3-AgentV1InjectAgentMessage
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-client-4-AgentV1SendFunctionCallResponse
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-client-5-AgentV1KeepAlive
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-client-6-AgentV1UpdatePrompt
          - $ref: >-
              #/components/messages/subpackage_agent/v1.agent.v1-client-7-AgentV1Media
servers:
  Production:
    url: wss://agent.deepgram.com/
    protocol: wss
    x-default: true
  Agent:
    url: wss://agent.deepgram.com/
    protocol: wss
components:
  messages:
    subpackage_agent/v1.agent.v1-server-0-AgentV1ReceiveFunctionCallResponse:
      name: AgentV1ReceiveFunctionCallResponse
      title: AgentV1ReceiveFunctionCallResponse
      description: |
        Receive a function call response from the server after the server
        has executed a server-side function call internally. This occurs
        when functions are marked with `client_side: false`.
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1ReceiveFunctionCallResponse'
    subpackage_agent/v1.agent.v1-server-1-AgentV1PromptUpdated:
      name: AgentV1PromptUpdated
      title: AgentV1PromptUpdated
      description: Receive prompt update from Deepgram's Voice Agent API
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1PromptUpdated'
    subpackage_agent/v1.agent.v1-server-2-AgentV1SpeakUpdated:
      name: AgentV1SpeakUpdated
      title: AgentV1SpeakUpdated
      description: Receive speak update from Deepgram's Voice Agent API
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1SpeakUpdated'
    subpackage_agent/v1.agent.v1-server-3-AgentV1InjectionRefused:
      name: AgentV1InjectionRefused
      title: AgentV1InjectionRefused
      description: Receive injection refused message from Deepgram's Voice Agent API
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1InjectionRefused'
    subpackage_agent/v1.agent.v1-server-4-AgentV1Welcome:
      name: AgentV1Welcome
      title: AgentV1Welcome
      description: Receive welcome message from Deepgram's Voice Agent API
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1Welcome'
    subpackage_agent/v1.agent.v1-server-5-AgentV1SettingsApplied:
      name: AgentV1SettingsApplied
      title: AgentV1SettingsApplied
      description: Receive settings applied message from Deepgram's Voice Agent API
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1SettingsApplied'
    subpackage_agent/v1.agent.v1-server-6-AgentV1ConversationText:
      name: AgentV1ConversationText
      title: AgentV1ConversationText
      description: Receive conversation text from Deepgram's Voice Agent API
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1ConversationText'
    subpackage_agent/v1.agent.v1-server-7-AgentV1UserStartedSpeaking:
      name: AgentV1UserStartedSpeaking
      title: AgentV1UserStartedSpeaking
      description: Receive user started speaking message from Deepgram's Voice Agent API
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1UserStartedSpeaking'
    subpackage_agent/v1.agent.v1-server-8-AgentV1AgentThinking:
      name: AgentV1AgentThinking
      title: AgentV1AgentThinking
      description: Receive agent thinking message from Deepgram's Voice Agent API
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1AgentThinking'
    subpackage_agent/v1.agent.v1-server-9-AgentV1FunctionCallRequest:
      name: AgentV1FunctionCallRequest
      title: AgentV1FunctionCallRequest
      description: Receive function call request from Deepgram's Voice Agent API
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1FunctionCallRequest'
    subpackage_agent/v1.agent.v1-server-10-AgentV1AgentStartedSpeaking:
      name: AgentV1AgentStartedSpeaking
      title: AgentV1AgentStartedSpeaking
      description: Receive agent started speaking message from Deepgram's Voice Agent API
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1AgentStartedSpeaking'
    subpackage_agent/v1.agent.v1-server-11-AgentV1AgentAudioDone:
      name: AgentV1AgentAudioDone
      title: AgentV1AgentAudioDone
      description: Receive agent audio done message from Deepgram's Voice Agent API
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1AgentAudioDone'
    subpackage_agent/v1.agent.v1-server-12-AgentV1Error:
      name: AgentV1Error
      title: AgentV1Error
      description: Receive error response from Deepgram's Voice Agent API
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1Error'
    subpackage_agent/v1.agent.v1-server-13-AgentV1Warning:
      name: AgentV1Warning
      title: AgentV1Warning
      description: Receive warning messages from Deepgram's Voice Agent API
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1Warning'
    subpackage_agent/v1.agent.v1-server-14-AgentV1Audio:
      name: AgentV1Audio
      title: AgentV1Audio
      description: Receive raw binary audio data generated by Deepgram's Voice Agent API
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1Audio'
    subpackage_agent/v1.agent.v1-client-0-AgentV1Settings:
      name: AgentV1Settings
      title: AgentV1Settings
      description: Send settings configuration to Deepgram's Voice Agent API
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1Settings'
    subpackage_agent/v1.agent.v1-client-1-AgentV1UpdateSpeak:
      name: AgentV1UpdateSpeak
      title: AgentV1UpdateSpeak
      description: Send update speak to Deepgram's Voice Agent API
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1UpdateSpeak'
    subpackage_agent/v1.agent.v1-client-2-AgentV1InjectUserMessage:
      name: AgentV1InjectUserMessage
      title: AgentV1InjectUserMessage
      description: Send inject user message to Deepgram's Voice Agent API
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1InjectUserMessage'
    subpackage_agent/v1.agent.v1-client-3-AgentV1InjectAgentMessage:
      name: AgentV1InjectAgentMessage
      title: AgentV1InjectAgentMessage
      description: Send inject agent message to Deepgram's Voice Agent API
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1InjectAgentMessage'
    subpackage_agent/v1.agent.v1-client-4-AgentV1SendFunctionCallResponse:
      name: AgentV1SendFunctionCallResponse
      title: AgentV1SendFunctionCallResponse
      description: |
        Send a function call response from the client to the server after
        executing a client-side function call. This is used when the server
        requests execution of a function marked with `client_side: true`.
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1SendFunctionCallResponse'
    subpackage_agent/v1.agent.v1-client-5-AgentV1KeepAlive:
      name: AgentV1KeepAlive
      title: AgentV1KeepAlive
      description: Send keep alive to Deepgram's Voice Agent API
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1KeepAlive'
    subpackage_agent/v1.agent.v1-client-6-AgentV1UpdatePrompt:
      name: AgentV1UpdatePrompt
      title: AgentV1UpdatePrompt
      description: Send a prompt update to Deepgram's Voice Agent API
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1UpdatePrompt'
    subpackage_agent/v1.agent.v1-client-7-AgentV1Media:
      name: AgentV1Media
      title: AgentV1Media
      description: Send raw binary audio data to Deepgram's Voice Agent API for processing
      payload:
        $ref: '#/components/schemas/AgentV1_AgentV1Media'
  schemas:
    AgentV1_AgentV1ReceiveFunctionCallResponse:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: FunctionCallResponse
        id:
          type: string
        name:
          type: string
        content:
          type: string
      required:
        - type
        - name
        - content
    AgentV1_AgentV1PromptUpdated:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: PromptUpdated
      required:
        - type
    AgentV1_AgentV1SpeakUpdated:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: SpeakUpdated
      required:
        - type
    AgentV1_AgentV1InjectionRefused:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: InjectionRefused
        message:
          type: string
      required:
        - type
        - message
    AgentV1_AgentV1Welcome:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: Welcome
        request_id:
          type: string
      required:
        - type
        - request_id
    AgentV1_AgentV1SettingsApplied:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: SettingsApplied
      required:
        - type
    ChannelsAgentV1MessagesAgentV1ConversationTextRole:
      type: string
      enum:
        - value: user
        - value: assistant
    AgentV1_AgentV1ConversationText:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: ConversationText
        role:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1ConversationTextRole
        content:
          type: string
      required:
        - type
        - role
        - content
    AgentV1_AgentV1UserStartedSpeaking:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: UserStartedSpeaking
      required:
        - type
    AgentV1_AgentV1AgentThinking:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: AgentThinking
        content:
          type: string
      required:
        - type
        - content
    ChannelsAgentV1MessagesAgentV1FunctionCallRequestFunctionsItems:
      type: object
      properties:
        id:
          type: string
        name:
          type: string
        arguments:
          type: string
        client_side:
          type: boolean
      required:
        - id
        - name
        - arguments
        - client_side
    AgentV1_AgentV1FunctionCallRequest:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: FunctionCallRequest
        functions:
          type: array
          items:
            $ref: >-
              #/components/schemas/ChannelsAgentV1MessagesAgentV1FunctionCallRequestFunctionsItems
      required:
        - type
        - functions
    AgentV1_AgentV1AgentStartedSpeaking:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: AgentStartedSpeaking
        total_latency:
          type: number
          format: double
        tts_latency:
          type: number
          format: double
        ttt_latency:
          type: number
          format: double
      required:
        - type
        - total_latency
        - tts_latency
        - ttt_latency
    AgentV1_AgentV1AgentAudioDone:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: AgentAudioDone
      required:
        - type
    ChannelsAgentV1MessagesAgentV1ErrorType:
      type: string
      enum:
        - value: Error
    AgentV1_AgentV1Error:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ChannelsAgentV1MessagesAgentV1ErrorType'
        description:
          type: string
        code:
          type: string
      required:
        - type
        - description
        - code
    ChannelsAgentV1MessagesAgentV1WarningType:
      type: string
      enum:
        - value: Warning
    AgentV1_AgentV1Warning:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ChannelsAgentV1MessagesAgentV1WarningType'
        description:
          type: string
        code:
          type: string
      required:
        - type
        - description
        - code
    AgentV1_AgentV1Audio:
      type: string
      format: binary
    ChannelsAgentV1MessagesAgentV1SettingsFlags:
      type: object
      properties:
        history:
          type: boolean
    ChannelsAgentV1MessagesAgentV1SettingsAudioInputEncoding:
      type: string
      enum:
        - value: linear16
        - value: linear32
        - value: flac
        - value: alaw
        - value: mulaw
        - value: amr-nb
        - value: amr-wb
        - value: opus
        - value: ogg-opus
        - value: speex
        - value: g729
    ChannelsAgentV1MessagesAgentV1SettingsAudioInput:
      type: object
      properties:
        encoding:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAudioInputEncoding
        sample_rate:
          type: number
          format: double
      required:
        - encoding
        - sample_rate
    ChannelsAgentV1MessagesAgentV1SettingsAudioOutputEncoding:
      type: string
      enum:
        - value: linear16
        - value: mulaw
        - value: alaw
    ChannelsAgentV1MessagesAgentV1SettingsAudioOutput:
      type: object
      properties:
        encoding:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAudioOutputEncoding
        sample_rate:
          type: number
          format: double
        bitrate:
          type: number
          format: double
        container:
          type: string
    ChannelsAgentV1MessagesAgentV1SettingsAudio:
      type: object
      properties:
        input:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAudioInput
        output:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAudioOutput
    ChannelsAgentV1MessagesAgentV1SettingsAgentContextMessagesItemsOneOf0Role:
      type: string
      enum:
        - value: user
        - value: assistant
    ChannelsAgentV1MessagesAgentV1SettingsAgentContextMessagesItems0:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: History
        role:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentContextMessagesItemsOneOf0Role
        content:
          type: string
      required:
        - type
        - role
        - content
    ChannelsAgentV1MessagesAgentV1SettingsAgentContextMessagesItemsOneOf1FunctionCallsItems:
      type: object
      properties:
        id:
          type: string
        name:
          type: string
        client_side:
          type: boolean
        arguments:
          type: string
        response:
          type: string
      required:
        - id
        - name
        - client_side
        - arguments
        - response
    ChannelsAgentV1MessagesAgentV1SettingsAgentContextMessagesItems1:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: History
        function_calls:
          type: array
          items:
            $ref: >-
              #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentContextMessagesItemsOneOf1FunctionCallsItems
      required:
        - type
        - function_calls
    ChannelsAgentV1MessagesAgentV1SettingsAgentContextMessagesItems:
      oneOf:
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentContextMessagesItems0
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentContextMessagesItems1
    ChannelsAgentV1MessagesAgentV1SettingsAgentContext:
      type: object
      properties:
        messages:
          type: array
          items:
            $ref: >-
              #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentContextMessagesItems
    ChannelsAgentV1MessagesAgentV1SettingsAgentListenProviderType:
      type: string
      enum:
        - value: deepgram
    ChannelsAgentV1MessagesAgentV1SettingsAgentListenProvider:
      type: object
      properties:
        type:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentListenProviderType
        model:
          type: string
        keyterms:
          type: array
          items:
            type: string
        smart_format:
          type: boolean
      required:
        - type
    ChannelsAgentV1MessagesAgentV1SettingsAgentListen:
      type: object
      properties:
        provider:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentListenProvider
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf0Type:
      type: string
      enum:
        - value: open_ai
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf0Model:
      type: string
      enum:
        - value: gpt-5
        - value: gpt-5-mini
        - value: gpt-5-nano
        - value: gpt-4.1
        - value: gpt-4.1-mini
        - value: gpt-4.1-nano
        - value: gpt-4o
        - value: gpt-4o-mini
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProvider0:
      type: object
      properties:
        type:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf0Type
        model:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf0Model
        temperature:
          type: number
          format: double
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf1Type:
      type: string
      enum:
        - value: aws_bedrock
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf1Model:
      type: string
      enum:
        - value: anthropic/claude-3-5-sonnet-20240620-v1:0
        - value: anthropic/claude-3-5-haiku-20240307-v1:0
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf1CredentialsType:
      type: string
      enum:
        - value: sts
        - value: iam
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf1Credentials:
      type: object
      properties:
        type:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf1CredentialsType
        region:
          type: string
        access_key_id:
          type: string
        secret_access_key:
          type: string
        session_token:
          type: string
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProvider1:
      type: object
      properties:
        type:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf1Type
        model:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf1Model
        temperature:
          type: number
          format: double
        credentials:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf1Credentials
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf2Type:
      type: string
      enum:
        - value: anthropic
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf2Model:
      type: string
      enum:
        - value: claude-3-5-haiku-latest
        - value: claude-sonnet-4-20250514
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProvider2:
      type: object
      properties:
        type:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf2Type
        model:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf2Model
        temperature:
          type: number
          format: double
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf3Type:
      type: string
      enum:
        - value: google
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf3Model:
      type: string
      enum:
        - value: gemini-2.0-flash
        - value: gemini-2.0-flash-lite
        - value: gemini-2.5-flash
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProvider3:
      type: object
      properties:
        type:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf3Type
        model:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf3Model
        temperature:
          type: number
          format: double
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf4Type:
      type: string
      enum:
        - value: groq
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf4Model:
      type: string
      enum:
        - value: openai/gpt-oss-20b
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProvider4:
      type: object
      properties:
        type:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf4Type
        model:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProviderOneOf4Model
        temperature:
          type: number
          format: double
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProvider:
      oneOf:
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProvider0
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProvider1
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProvider2
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProvider3
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProvider4
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkEndpoint:
      type: object
      properties:
        url:
          type: string
        headers:
          type: object
          additionalProperties:
            type: string
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkFunctionsItemsParameters:
      type: object
      properties: {}
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkFunctionsItemsEndpoint:
      type: object
      properties:
        url:
          type: string
        method:
          type: string
        headers:
          type: object
          additionalProperties:
            type: string
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkFunctionsItems:
      type: object
      properties:
        name:
          type: string
        description:
          type: string
        parameters:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkFunctionsItemsParameters
        endpoint:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkFunctionsItemsEndpoint
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkContextLength0:
      type: string
      enum:
        - value: max
    ChannelsAgentV1MessagesAgentV1SettingsAgentThinkContextLength:
      oneOf:
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkContextLength0
        - type: number
          format: double
    ChannelsAgentV1MessagesAgentV1SettingsAgentThink:
      type: object
      properties:
        provider:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkProvider
        endpoint:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkEndpoint
        functions:
          type: array
          items:
            $ref: >-
              #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkFunctionsItems
        prompt:
          type: string
        context_length:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThinkContextLength
      required:
        - provider
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0ProviderOneOf0Model:
      type: string
      enum:
        - value: aura-asteria-en
        - value: aura-luna-en
        - value: aura-stella-en
        - value: aura-athena-en
        - value: aura-hera-en
        - value: aura-orion-en
        - value: aura-arcas-en
        - value: aura-perseus-en
        - value: aura-angus-en
        - value: aura-orpheus-en
        - value: aura-helios-en
        - value: aura-zeus-en
        - value: aura-2-amalthea-en
        - value: aura-2-andromeda-en
        - value: aura-2-apollo-en
        - value: aura-2-arcas-en
        - value: aura-2-aries-en
        - value: aura-2-asteria-en
        - value: aura-2-athena-en
        - value: aura-2-atlas-en
        - value: aura-2-aurora-en
        - value: aura-2-callista-en
        - value: aura-2-cora-en
        - value: aura-2-cordelia-en
        - value: aura-2-delia-en
        - value: aura-2-draco-en
        - value: aura-2-electra-en
        - value: aura-2-harmonia-en
        - value: aura-2-helena-en
        - value: aura-2-hera-en
        - value: aura-2-hermes-en
        - value: aura-2-hyperion-en
        - value: aura-2-iris-en
        - value: aura-2-janus-en
        - value: aura-2-juno-en
        - value: aura-2-jupiter-en
        - value: aura-2-luna-en
        - value: aura-2-mars-en
        - value: aura-2-minerva-en
        - value: aura-2-neptune-en
        - value: aura-2-odysseus-en
        - value: aura-2-ophelia-en
        - value: aura-2-orion-en
        - value: aura-2-orpheus-en
        - value: aura-2-pandora-en
        - value: aura-2-phoebe-en
        - value: aura-2-pluto-en
        - value: aura-2-saturn-en
        - value: aura-2-selene-en
        - value: aura-2-thalia-en
        - value: aura-2-theia-en
        - value: aura-2-vesta-en
        - value: aura-2-zeus-en
        - value: aura-2-sirio-es
        - value: aura-2-nestor-es
        - value: aura-2-carina-es
        - value: aura-2-celeste-es
        - value: aura-2-alvaro-es
        - value: aura-2-diana-es
        - value: aura-2-aquila-es
        - value: aura-2-selena-es
        - value: aura-2-estrella-es
        - value: aura-2-javier-es
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0Provider0:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: deepgram
        model:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0ProviderOneOf0Model
      required:
        - type
        - model
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0ProviderOneOf1ModelId:
      type: string
      enum:
        - value: eleven_turbo_v2_5
        - value: eleven_monolingual_v1
        - value: eleven_multilingual_v2
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0Provider1:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: eleven_labs
        model_id:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0ProviderOneOf1ModelId
        language_code:
          type: string
      required:
        - type
        - model_id
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0ProviderOneOf2ModelId:
      type: string
      enum:
        - value: sonic-2
        - value: sonic-multilingual
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0ProviderOneOf2Voice:
      type: object
      properties:
        mode:
          type: string
        id:
          type: string
      required:
        - mode
        - id
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0Provider2:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: cartesia
        model_id:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0ProviderOneOf2ModelId
        voice:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0ProviderOneOf2Voice
        language:
          type: string
      required:
        - type
        - model_id
        - voice
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0ProviderOneOf3Model:
      type: string
      enum:
        - value: tts-1
        - value: tts-1-hd
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0ProviderOneOf3Voice:
      type: string
      enum:
        - value: alloy
        - value: echo
        - value: fable
        - value: onyx
        - value: nova
        - value: shimmer
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0Provider3:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: open_ai
        model:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0ProviderOneOf3Model
        voice:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0ProviderOneOf3Voice
      required:
        - type
        - model
        - voice
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0ProviderOneOf4Voice:
      type: string
      enum:
        - value: Matthew
        - value: Joanna
        - value: Amy
        - value: Emma
        - value: Brian
        - value: Arthur
        - value: Aria
        - value: Ayanda
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0ProviderOneOf4Engine:
      type: string
      enum:
        - value: generative
        - value: long-form
        - value: standard
        - value: neural
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0ProviderOneOf4CredentialsType:
      type: string
      enum:
        - value: sts
        - value: iam
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0ProviderOneOf4Credentials:
      type: object
      properties:
        type:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0ProviderOneOf4CredentialsType
        region:
          type: string
        access_key_id:
          type: string
        secret_access_key:
          type: string
        session_token:
          type: string
      required:
        - type
        - region
        - access_key_id
        - secret_access_key
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0Provider4:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: aws_polly
        voice:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0ProviderOneOf4Voice
        language_code:
          type: string
        engine:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0ProviderOneOf4Engine
        credentials:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0ProviderOneOf4Credentials
      required:
        - type
        - voice
        - language_code
        - engine
        - credentials
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0Provider:
      oneOf:
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0Provider0
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0Provider1
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0Provider2
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0Provider3
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0Provider4
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0Endpoint:
      type: object
      properties:
        url:
          type: string
        headers:
          type: object
          additionalProperties:
            type: string
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeak0:
      type: object
      properties:
        provider:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0Provider
        endpoint:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf0Endpoint
      required:
        - provider
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProviderOneOf0Model:
      type: string
      enum:
        - value: aura-asteria-en
        - value: aura-luna-en
        - value: aura-stella-en
        - value: aura-athena-en
        - value: aura-hera-en
        - value: aura-orion-en
        - value: aura-arcas-en
        - value: aura-perseus-en
        - value: aura-angus-en
        - value: aura-orpheus-en
        - value: aura-helios-en
        - value: aura-zeus-en
        - value: aura-2-amalthea-en
        - value: aura-2-andromeda-en
        - value: aura-2-apollo-en
        - value: aura-2-arcas-en
        - value: aura-2-aries-en
        - value: aura-2-asteria-en
        - value: aura-2-athena-en
        - value: aura-2-atlas-en
        - value: aura-2-aurora-en
        - value: aura-2-callista-en
        - value: aura-2-cora-en
        - value: aura-2-cordelia-en
        - value: aura-2-delia-en
        - value: aura-2-draco-en
        - value: aura-2-electra-en
        - value: aura-2-harmonia-en
        - value: aura-2-helena-en
        - value: aura-2-hera-en
        - value: aura-2-hermes-en
        - value: aura-2-hyperion-en
        - value: aura-2-iris-en
        - value: aura-2-janus-en
        - value: aura-2-juno-en
        - value: aura-2-jupiter-en
        - value: aura-2-luna-en
        - value: aura-2-mars-en
        - value: aura-2-minerva-en
        - value: aura-2-neptune-en
        - value: aura-2-odysseus-en
        - value: aura-2-ophelia-en
        - value: aura-2-orion-en
        - value: aura-2-orpheus-en
        - value: aura-2-pandora-en
        - value: aura-2-phoebe-en
        - value: aura-2-pluto-en
        - value: aura-2-saturn-en
        - value: aura-2-selene-en
        - value: aura-2-thalia-en
        - value: aura-2-theia-en
        - value: aura-2-vesta-en
        - value: aura-2-zeus-en
        - value: aura-2-sirio-es
        - value: aura-2-nestor-es
        - value: aura-2-carina-es
        - value: aura-2-celeste-es
        - value: aura-2-alvaro-es
        - value: aura-2-diana-es
        - value: aura-2-aquila-es
        - value: aura-2-selena-es
        - value: aura-2-estrella-es
        - value: aura-2-javier-es
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProvider0:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: deepgram
        model:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProviderOneOf0Model
      required:
        - type
        - model
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProviderOneOf1ModelId:
      type: string
      enum:
        - value: eleven_turbo_v2_5
        - value: eleven_monolingual_v1
        - value: eleven_multilingual_v2
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProvider1:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: eleven_labs
        model_id:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProviderOneOf1ModelId
        language_code:
          type: string
      required:
        - type
        - model_id
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProviderOneOf2ModelId:
      type: string
      enum:
        - value: sonic-2
        - value: sonic-multilingual
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProviderOneOf2Voice:
      type: object
      properties:
        mode:
          type: string
        id:
          type: string
      required:
        - mode
        - id
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProvider2:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: cartesia
        model_id:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProviderOneOf2ModelId
        voice:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProviderOneOf2Voice
        language:
          type: string
      required:
        - type
        - model_id
        - voice
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProviderOneOf3Model:
      type: string
      enum:
        - value: tts-1
        - value: tts-1-hd
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProviderOneOf3Voice:
      type: string
      enum:
        - value: alloy
        - value: echo
        - value: fable
        - value: onyx
        - value: nova
        - value: shimmer
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProvider3:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: open_ai
        model:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProviderOneOf3Model
        voice:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProviderOneOf3Voice
      required:
        - type
        - model
        - voice
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProviderOneOf4Voice:
      type: string
      enum:
        - value: Matthew
        - value: Joanna
        - value: Amy
        - value: Emma
        - value: Brian
        - value: Arthur
        - value: Aria
        - value: Ayanda
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProviderOneOf4Engine:
      type: string
      enum:
        - value: generative
        - value: long-form
        - value: standard
        - value: neural
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProviderOneOf4CredentialsType:
      type: string
      enum:
        - value: sts
        - value: iam
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProviderOneOf4Credentials:
      type: object
      properties:
        type:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProviderOneOf4CredentialsType
        region:
          type: string
        access_key_id:
          type: string
        secret_access_key:
          type: string
        session_token:
          type: string
      required:
        - type
        - region
        - access_key_id
        - secret_access_key
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProvider4:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: aws_polly
        voice:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProviderOneOf4Voice
        language_code:
          type: string
        engine:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProviderOneOf4Engine
        credentials:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProviderOneOf4Credentials
      required:
        - type
        - voice
        - language_code
        - engine
        - credentials
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProvider:
      oneOf:
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProvider0
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProvider1
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProvider2
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProvider3
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProvider4
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsEndpoint:
      type: object
      properties:
        url:
          type: string
        headers:
          type: object
          additionalProperties:
            type: string
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1Items:
      type: object
      properties:
        provider:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsProvider
        endpoint:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1ItemsEndpoint
      required:
        - provider
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeak1:
      type: array
      items:
        $ref: >-
          #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeakOneOf1Items
    ChannelsAgentV1MessagesAgentV1SettingsAgentSpeak:
      oneOf:
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeak0
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeak1
    ChannelsAgentV1MessagesAgentV1SettingsAgent:
      type: object
      properties:
        language:
          type: string
        context:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentContext
        listen:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentListen
        think:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentThink
        speak:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgentSpeak
        greeting:
          type: string
    AgentV1_AgentV1Settings:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: Settings
        tags:
          type: array
          items:
            type: string
        experimental:
          type: boolean
        flags:
          $ref: '#/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsFlags'
        mip_opt_out:
          type: boolean
        audio:
          $ref: '#/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAudio'
        agent:
          $ref: '#/components/schemas/ChannelsAgentV1MessagesAgentV1SettingsAgent'
      required:
        - type
        - audio
        - agent
    ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProviderOneOf0Model:
      type: string
      enum:
        - value: aura-asteria-en
        - value: aura-luna-en
        - value: aura-stella-en
        - value: aura-athena-en
        - value: aura-hera-en
        - value: aura-orion-en
        - value: aura-arcas-en
        - value: aura-perseus-en
        - value: aura-angus-en
        - value: aura-orpheus-en
        - value: aura-helios-en
        - value: aura-zeus-en
        - value: aura-2-amalthea-en
        - value: aura-2-andromeda-en
        - value: aura-2-apollo-en
        - value: aura-2-arcas-en
        - value: aura-2-aries-en
        - value: aura-2-asteria-en
        - value: aura-2-athena-en
        - value: aura-2-atlas-en
        - value: aura-2-aurora-en
        - value: aura-2-callista-en
        - value: aura-2-cora-en
        - value: aura-2-cordelia-en
        - value: aura-2-delia-en
        - value: aura-2-draco-en
        - value: aura-2-electra-en
        - value: aura-2-harmonia-en
        - value: aura-2-helena-en
        - value: aura-2-hera-en
        - value: aura-2-hermes-en
        - value: aura-2-hyperion-en
        - value: aura-2-iris-en
        - value: aura-2-janus-en
        - value: aura-2-juno-en
        - value: aura-2-jupiter-en
        - value: aura-2-luna-en
        - value: aura-2-mars-en
        - value: aura-2-minerva-en
        - value: aura-2-neptune-en
        - value: aura-2-odysseus-en
        - value: aura-2-ophelia-en
        - value: aura-2-orion-en
        - value: aura-2-orpheus-en
        - value: aura-2-pandora-en
        - value: aura-2-phoebe-en
        - value: aura-2-pluto-en
        - value: aura-2-saturn-en
        - value: aura-2-selene-en
        - value: aura-2-thalia-en
        - value: aura-2-theia-en
        - value: aura-2-vesta-en
        - value: aura-2-zeus-en
        - value: aura-2-sirio-es
        - value: aura-2-nestor-es
        - value: aura-2-carina-es
        - value: aura-2-celeste-es
        - value: aura-2-alvaro-es
        - value: aura-2-diana-es
        - value: aura-2-aquila-es
        - value: aura-2-selena-es
        - value: aura-2-estrella-es
        - value: aura-2-javier-es
    ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProvider0:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: deepgram
        model:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProviderOneOf0Model
      required:
        - type
        - model
    ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProviderOneOf1ModelId:
      type: string
      enum:
        - value: eleven_turbo_v2_5
        - value: eleven_monolingual_v1
        - value: eleven_multilingual_v2
    ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProvider1:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: eleven_labs
        model_id:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProviderOneOf1ModelId
        language_code:
          type: string
      required:
        - type
        - model_id
    ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProviderOneOf2ModelId:
      type: string
      enum:
        - value: sonic-2
        - value: sonic-multilingual
    ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProviderOneOf2Voice:
      type: object
      properties:
        mode:
          type: string
        id:
          type: string
      required:
        - mode
        - id
    ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProvider2:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: cartesia
        model_id:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProviderOneOf2ModelId
        voice:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProviderOneOf2Voice
        language:
          type: string
      required:
        - type
        - model_id
        - voice
    ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProviderOneOf3Model:
      type: string
      enum:
        - value: tts-1
        - value: tts-1-hd
    ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProviderOneOf3Voice:
      type: string
      enum:
        - value: alloy
        - value: echo
        - value: fable
        - value: onyx
        - value: nova
        - value: shimmer
    ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProvider3:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: open_ai
        model:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProviderOneOf3Model
        voice:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProviderOneOf3Voice
      required:
        - type
        - model
        - voice
    ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProviderOneOf4Voice:
      type: string
      enum:
        - value: Matthew
        - value: Joanna
        - value: Amy
        - value: Emma
        - value: Brian
        - value: Arthur
        - value: Aria
        - value: Ayanda
    ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProviderOneOf4Engine:
      type: string
      enum:
        - value: generative
        - value: long-form
        - value: standard
        - value: neural
    ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProviderOneOf4CredentialsType:
      type: string
      enum:
        - value: sts
        - value: iam
    ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProviderOneOf4Credentials:
      type: object
      properties:
        type:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProviderOneOf4CredentialsType
        region:
          type: string
        access_key_id:
          type: string
        secret_access_key:
          type: string
        session_token:
          type: string
      required:
        - type
        - region
        - access_key_id
        - secret_access_key
    ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProvider4:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: aws_polly
        voice:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProviderOneOf4Voice
        language_code:
          type: string
        engine:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProviderOneOf4Engine
        credentials:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProviderOneOf4Credentials
      required:
        - type
        - voice
        - language_code
        - engine
        - credentials
    ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProvider:
      oneOf:
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProvider0
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProvider1
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProvider2
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProvider3
        - $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProvider4
    ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakEndpoint:
      type: object
      properties:
        url:
          type: string
        headers:
          type: object
          additionalProperties:
            type: string
    ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeak:
      type: object
      properties:
        provider:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakProvider
        endpoint:
          $ref: >-
            #/components/schemas/ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeakEndpoint
      required:
        - provider
    AgentV1_AgentV1UpdateSpeak:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: UpdateSpeak
        speak:
          $ref: '#/components/schemas/ChannelsAgentV1MessagesAgentV1UpdateSpeakSpeak'
      required:
        - type
        - speak
    AgentV1_AgentV1InjectUserMessage:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: InjectUserMessage
        content:
          type: string
      required:
        - type
        - content
    AgentV1_AgentV1InjectAgentMessage:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: InjectAgentMessage
        message:
          type: string
      required:
        - type
        - message
    AgentV1_AgentV1SendFunctionCallResponse:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: FunctionCallResponse
        id:
          type: string
        name:
          type: string
        content:
          type: string
      required:
        - type
        - name
        - content
    ChannelsAgentV1MessagesAgentV1KeepAliveType:
      type: string
      enum:
        - value: KeepAlive
    AgentV1_AgentV1KeepAlive:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ChannelsAgentV1MessagesAgentV1KeepAliveType'
      required:
        - type
    AgentV1_AgentV1UpdatePrompt:
      type: object
      properties:
        type:
          type: string
          enum:
            - type: stringLiteral
              value: UpdatePrompt
        prompt:
          type: string
      required:
        - type
        - prompt
    AgentV1_AgentV1Media:
      type: string
      format: binary

```