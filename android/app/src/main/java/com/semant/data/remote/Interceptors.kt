package com.semant.data.remote

import com.semant.data.SettingsRepository
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject

/** Rewrites every request onto the base URL configured in Settings. */
class BaseUrlInterceptor @Inject constructor(private val settings: SettingsRepository) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val base = settings.baseUrlBlocking().toHttpUrlOrNull()
            ?: return chain.proceed(chain.request())
        val old = chain.request().url
        val newUrl = old.newBuilder()
            .scheme(base.scheme)
            .host(base.host)
            .port(base.port)
            .build()
        return chain.proceed(chain.request().newBuilder().url(newUrl).build())
    }
}

class ApiKeyInterceptor @Inject constructor(private val settings: SettingsRepository) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val key = settings.apiKeyBlocking()
        val request = if (key.isNotEmpty())
            chain.request().newBuilder().addHeader("X-API-Key", key).build()
        else chain.request()
        return chain.proceed(request)
    }
}
