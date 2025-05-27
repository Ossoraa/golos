<template>
  <div class="h-screen flex flex-col bg-gradient-to-b from-white to-green-300">
    <header class="bg-green-500 p-20 flex justify-center">
      <div class="relative">
        <div
          class="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-31 h-31 bg-white rounded-full flex justify-center items-center"
        >
          <img :src="isSpeaking ? '/kwa.gif' : '/frog.png'" alt="Frog" class="w-24 h-19" />
        </div>
      </div>
    </header>

    <main class="flex-1 relative overflow-y-auto p-8 items-center flex flex-col-reverse">
      <div
        class="absolute inset-0 bg-center bg-contain bg-no-repeat pointer-events-none opacity-10"
        style="
          background-image: url('/wallpaper.png');
          background-size: auto 60%;
          background-repeat: repeat;
        "
      ></div>

      <ul class="space-y-4 w-full max-w-2xl z-10">
        <li
          v-for="message in sortedMessages"
          :key="message.id"
          :class="['flex', message.fromMe ? 'justify-end' : 'justify-start']"
        >
          <div class="flex items-start space-x-2 max-w-[75%]">
            <div
              :class="[
                'p-4 rounded-xl whitespace-pre-wrap break-words',
                message.fromMe ? 'bg-white text-gray-900' : 'bg-green-400 text-white',
              ]"
            >
              {{ message.text }}
              <div
                v-if="!message.fromMe && !message.noFeedback"
                class="flex items-center space-x-2 mt-1"
              >
                <img
                  :src="message.like ? '/like2.png' : '/like.png'"
                  alt="Like"
                  class="w-6 h-6 cursor-pointer"
                  @click="toggleLike(message)"
                />
                <img
                  :src="message.dislike ? '/dislike2.png' : '/dislike.png'"
                  alt="Dislike"
                  class="w-6 h-6 cursor-pointer"
                  @click="toggleDislike(message)"
                />
              </div>
            </div>
          </div>
        </li>
      </ul>
    </main>

    <footer class="p-6">
      <form @submit.prevent="sendMessage" class="flex justify-center">
        <div class="relative w-full max-w-2xl">
          <input
            type="text"
            v-model="newMessage"
            :disabled="isBusy"
            :placeholder="placeholderText"
            @focus="isFocused = true"
            @blur="isFocused = false"
            class="w-full rounded-full bg-gray-100 px-6 py-4 pr-14 text-base focus:outline-none focus:ring-2 focus:ring-green-400 disabled:opacity-50"
          />
          <button
            type="submit"
            :disabled="isBusy"
            class="absolute right-4 top-1/2 transform -translate-y-1/2"
          >
            <img v-if="newMessage.trim()" src="/enter.png" alt="Enter" class="w-10 h-10" />
            <img
              v-else
              :src="isRecording ? '/recording.png' : '/microphone.png'"
              alt="Microphone"
              class="w-10 h-10"
              @click.prevent="toggleRecording"
            />
          </button>
        </div>
      </form>
    </footer>
  </div>
</template>

<script>
export default {
  data() {
    return {
      messages: [],
      newMessage: '',
      isRecording: false,
      isSpeaking: false,
      isBusy: false,
      isFocused: false,
      mediaRecorder: null,
      audioChunks: [],
      suggestions: [
        'Сколько у меня денег на карте?',
        'Какой курс доллара?',
        'Что такое СБП?',
        'Как взять кредит?',
        'Как получить выписку по счёту?',
      ],
      currentSuggestionIndex: 0,
      suggestionInterval: null,
    }
  },
  computed: {
    sortedMessages() {
      return this.messages
    },
    placeholderText() {
      if (this.isRecording) return 'Запись голосового сообщения...'
      if (this.isFocused) return 'Введите текст'
      return this.suggestions[this.currentSuggestionIndex]
    },
  },
  methods: {
    toggleLike(message) {
      message.like = !message.like
      if (message.like) message.dislike = false
    },
    toggleDislike(message) {
      message.dislike = !message.dislike
      if (message.dislike) message.like = false
    },
    async sendMessage() {
      const messageText = this.newMessage.trim()
      if (!messageText || this.isBusy) return

      const userMessage = {
        id: Date.now(),
        text: messageText,
        fromMe: true,
      }
      this.messages.push(userMessage)
      this.newMessage = ''
      this.isBusy = true

      const waitingId = Date.now() + 1
      this.messages.push({
        id: waitingId,
        text: 'Бот печатет...',
        fromMe: false,
      })

      try {
        const response = await fetch('http://localhost:8000/api/message', {
          method: 'POST',
          body: JSON.stringify({ text: messageText }),
          headers: { 'Content-Type': 'application/json' },
        })

        const data = await response.json()

        this.messages = this.messages.filter((msg) => msg.id !== waitingId)

        await this.typeText(data.answer, false)

        if (data.audio_url) {
          this.playAudioWithSpeaking(data.audio_url)
        } else {
          this.isBusy = false
        }
      } catch (error) {
        console.error('Бот не отвечает:', error)
        this.isBusy = false
        this.isSpeaking = false
      }
    },

    async toggleRecording() {
      if (this.isBusy) return

      if (this.isRecording) {
        this.mediaRecorder.stop()
        this.isRecording = false
      } else {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        this.mediaRecorder = new MediaRecorder(stream)
        this.audioChunks = []

        this.mediaRecorder.ondataavailable = (e) => this.audioChunks.push(e.data)

        this.mediaRecorder.onstop = async () => {
          const blob = new Blob(this.audioChunks, { type: 'audio/webm' })
          const formData = new FormData()
          formData.append('audio_file', blob, 'recording.webm')

          this.isBusy = true

          const waitingId = Date.now()
          this.messages.push({
            id: waitingId,
            text: 'Бот печатет...',
            fromMe: false,
          })

          const res = await fetch('http://localhost:8000/api/chat/voice', {
            method: 'POST',
            body: formData,
          })

          const data = await res.json()

          this.messages = this.messages.filter((msg) => msg.id !== waitingId)

          if (data.question) {
            this.messages.push({
              id: Date.now() + 1,
              text: data.question,
              fromMe: true,
            })
          }

          if (data.answer || data.text) {
            await this.typeText(data.answer || data.text, false)

            if (data.audio_url) {
              this.playAudioWithSpeaking(data.audio_url)
            } else {
              this.isBusy = false
              this.isSpeaking = false
            }
          } else {
            this.isBusy = false
            this.isSpeaking = false
          }
        }

        this.mediaRecorder.start()
        this.isRecording = true
      }
    },

    playAudioWithSpeaking(url) {
      this.isSpeaking = true
      const audio = new Audio(url)
      audio.play()
      audio.onended = () => {
        this.isSpeaking = false
        this.isBusy = false
      }
    },

    addMessage(text, fromMe = false, noFeedback = false) {
      this.messages.push({
        id: Date.now(),
        text,
        fromMe,
        like: false,
        dislike: false,
        noFeedback,
      })
    },

    async typeText(fullText, fromMe = false, delay = 20) {
      return new Promise((resolve) => {
        const id = Date.now()
        this.messages.push({ id, text: '', fromMe, like: false, dislike: false })

        let i = 0
        const interval = setInterval(() => {
          const msg = this.messages.find((m) => m.id === id)
          if (msg) {
            msg.text += fullText[i]
          }
          i++
          if (i >= fullText.length) {
            clearInterval(interval)
            resolve()
          }
        }, delay)
      })
    },
  },
  mounted() {
    this.addMessage(
      'Здравствуйте! Бот готов к работе. Я могу:\n> Сказать Ваш баланс\n> Сказать номер Вашей карты\n> Перевести деньги человеку по имени в контактах (назовите кому и сколько рублей хотите перевести)\n>...\nЧем могу помочь?',
      false,
      true, // отключаем лайки/дизлайки у стартового сообщения
    )

    this.suggestionInterval = setInterval(() => {
      this.currentSuggestionIndex = (this.currentSuggestionIndex + 1) % this.suggestions.length
    }, 7000)
  },
  beforeDestroy() {
    clearInterval(this.suggestionInterval)
  },
}
</script>

<style scoped></style>
