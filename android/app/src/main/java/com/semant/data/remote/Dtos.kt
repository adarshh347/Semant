package com.semant.data.remote

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

@Serializable
data class BoundingBoxDto(val x: Int, val y: Int, val width: Int, val height: Int)

@Serializable
data class TextBlockDto(val id: String? = null, val type: String, val content: String, val color: String? = null)

@Serializable
data class PostDto(
    val id: String,
    @SerialName("photo_url") val photoUrl: String,
    @SerialName("photo_public_id") val photoPublicId: String,
    @SerialName("updated_at") val updatedAt: String? = null,
    @SerialName("text_blocks") val textBlocks: List<TextBlockDto> = emptyList(),
    @SerialName("bounding_box_tags") val boundingBoxTags: Map<String, BoundingBoxDto>? = null,
    @SerialName("general_tags") val generalTags: List<String>? = null,
    @SerialName("source_url") val sourceUrl: String? = null,
    @SerialName("instagram_handle") val instagramHandle: String? = null,
    @SerialName("instagram_handles") val instagramHandles: List<String>? = null,
    @SerialName("source_account") val sourceAccount: JsonObject? = null,
    @SerialName("local_context") val localContext: JsonObject? = null,
    @SerialName("region_annotations") val regionAnnotations: List<JsonObject>? = null,
)

@Serializable
data class PaginatedPostsDto(
    val posts: List<PostDto>,
    @SerialName("total_pages") val totalPages: Int,
    @SerialName("current_page") val currentPage: Int,
)

@Serializable
data class UrlUploadRequestDto(
    @SerialName("image_url") val imageUrl: String,
    @SerialName("source_url") val sourceUrl: String? = null,
    @SerialName("general_tags") val generalTags: List<String> = emptyList(),
)
