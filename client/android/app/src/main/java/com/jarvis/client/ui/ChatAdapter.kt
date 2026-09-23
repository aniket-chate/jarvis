package com.jarvis.client.ui

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.jarvis.client.R
import com.jarvis.client.model.ChatMessage
import com.jarvis.client.model.MessageSender

/**
 * RecyclerView adapter for chat conversation stream.
 */
class ChatAdapter : ListAdapter<ChatMessage, RecyclerView.ViewHolder>(DiffCallback) {

    override fun getItemViewType(position: Int): Int {
        return when (getItem(position).sender) {
            MessageSender.USER -> VIEW_TYPE_USER
            MessageSender.JARVIS -> VIEW_TYPE_JARVIS
            MessageSender.SYSTEM -> VIEW_TYPE_SYSTEM
        }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): RecyclerView.ViewHolder {
        val inflater = LayoutInflater.from(parent.context)
        return when (viewType) {
            VIEW_TYPE_USER -> {
                val view = inflater.inflate(R.layout.item_message_user, parent, false)
                UserViewHolder(view)
            }
            else -> {
                val view = inflater.inflate(R.layout.item_message_jarvis, parent, false)
                JarvisViewHolder(view)
            }
        }
    }

    override fun onBindViewHolder(holder: RecyclerView.ViewHolder, position: Int) {
        val message = getItem(position)
        when (holder) {
            is UserViewHolder -> holder.bind(message)
            is JarvisViewHolder -> holder.bind(message)
        }
    }

    class UserViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
        private val tvMessage: TextView = itemView.findViewById(R.id.tvUserMessage)
        private val tvTimestamp: TextView = itemView.findViewById(R.id.tvUserTimestamp)

        fun bind(msg: ChatMessage) {
            tvMessage.text = msg.text
            tvTimestamp.text = msg.formattedTime
        }
    }

    class JarvisViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
        private val tvMessage: TextView = itemView.findViewById(R.id.tvJarvisMessage)
        private val tvTimestamp: TextView = itemView.findViewById(R.id.tvJarvisTimestamp)
        private val tvIntentBadge: TextView = itemView.findViewById(R.id.tvIntentBadge)

        fun bind(msg: ChatMessage) {
            tvMessage.text = msg.text
            tvTimestamp.text = msg.formattedTime
            if (msg.intent.isNullOrBlank()) {
                tvIntentBadge.visibility = View.GONE
            } else {
                tvIntentBadge.visibility = View.VISIBLE
                tvIntentBadge.text = msg.intent
            }
        }
    }

    companion object {
        private const val VIEW_TYPE_USER = 1
        private const val VIEW_TYPE_JARVIS = 2
        private const val VIEW_TYPE_SYSTEM = 3

        private val DiffCallback = object : DiffUtil.ItemCallback<ChatMessage>() {
            override fun areItemsTheSame(oldItem: ChatMessage, newItem: ChatMessage): Boolean {
                return oldItem.id == newItem.id
            }

            override fun areContentsTheSame(oldItem: ChatMessage, newItem: ChatMessage): Boolean {
                return oldItem == newItem
            }
        }
    }
}
