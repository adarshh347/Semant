# Semant Android App — Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Native Android app that captures images shared from any app (WhatsApp, Twitter, Chrome) into the Semant backend via an offline-safe queue, and browses the gallery — plus API-key auth on the backend.

**Architecture:** Single `:app` Gradle module in `android/`, MVVM (Compose screens → ViewModels → repositories). Share Sheet intents land in a translucent `ShareActivity` that writes to a Room queue; a WorkManager worker uploads to the existing FastAPI endpoints. Design doc: `docs/plans/2026-07-03-android-app-design.md`.

**Tech Stack:** Kotlin 2.x, Jetpack Compose (Material 3), Hilt, Retrofit + kotlinx-serialization, OkHttp, Coil, Room, WorkManager, Paging 3, DataStore. Backend: FastAPI (existing).

**Version note:** Library versions below were current at plan time. If Gradle fails to resolve one, bump to the latest stable — do not downgrade code to fit old versions.

**Backend API facts (verified against `backend/routers/posts.py`):**
- `GET /api/v1/posts/?page=&limit=&tag=` → `{posts: [...], total_pages, current_page}`
- `GET /api/v1/posts/{id}` → Post
- `POST /api/v1/posts/` multipart: part `file` (image bytes) + form field `general_tags_str` (comma-separated) → 201 Post
- `POST /api/v1/posts/upload-from-url` JSON `{image_url, source_url?, general_tags?}` → 201 Post
- `GET /api/v1/posts/tags/` → `["tag1", ...]`
- `GET /health` → open, no auth
- Post JSON fields: `id, photo_url, photo_public_id, updated_at, text_blocks, bounding_box_tags {name: {x,y,width,height}}, general_tags, source_url, instagram_handle, instagram_handles, source_account, local_context, region_annotations`

---

## Task 0: Android toolchain setup (one-time, needs the human for sudo)

Nothing Android exists on this machine (no Java, no SDK, no adb). Everything below is command-line; Android Studio is optional but recommended for the emulator.

**Step 1: Install JDK 17 and tools**

```bash
sudo apt update && sudo apt install -y openjdk-17-jdk unzip
java -version   # expect: openjdk 17.x
```

**Step 2: Install Android SDK command-line tools**

```bash
mkdir -p ~/Android/Sdk/cmdline-tools
cd ~/Android/Sdk/cmdline-tools
# Get the current "commandlinetools-linux" zip URL from https://developer.android.com/studio#command-line-tools-only
wget https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -O tools.zip
unzip tools.zip && mv cmdline-tools latest && rm tools.zip
```

**Step 3: Environment variables** (fish shell — `~/.config/fish/config.fish`)

```fish
set -gx ANDROID_HOME $HOME/Android/Sdk
fish_add_path $ANDROID_HOME/cmdline-tools/latest/bin $ANDROID_HOME/platform-tools
```

**Step 4: SDK packages + licenses**

```bash
sdkmanager "platform-tools" "platforms;android-35" "build-tools;35.0.0"
sdkmanager --licenses   # accept all
```

**Step 5: Gradle (only to bootstrap the wrapper once)**

```bash
sudo snap install gradle --classic   # or SDKMAN
```

**Step 6 (recommended): Android Studio** — `sudo snap install android-studio --classic` — for the emulator and Compose previews. Not required for CLI builds.

**Step 7: Verify** — `adb --version` and `sdkmanager --list_installed` show platform-tools, android-35, build-tools.

---

## Task 1: Backend — X-API-Key auth (TDD)

**Files:**
- Create: `backend/security.py`
- Create: `backend/tests/__init__.py`, `backend/tests/test_auth.py`
- Modify: `backend/config.py` (add `API_KEY`)
- Modify: `backend/main.py` (apply dependency to routers)

**Behavior:** If `API_KEY` env var is unset → auth disabled (local dev unchanged). If set → every `/api/v1/*` request must send matching `X-API-Key` header or get 401. `/health` always open.

**Step 1: Install test deps into the venv**

```bash
cd /home/adarsh-yadav/Documents/projects/semant
source venv/bin/activate 2>/dev/null || python3 -m venv venv && source venv/bin/activate
pip install pytest httpx
```

**Step 2: Write the failing test** — `backend/tests/test_auth.py`:

```python
import pytest
from fastapi import HTTPException

from backend.config import settings
from backend.security import require_api_key


@pytest.mark.anyio
async def test_no_key_configured_allows_all(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", None)
    await require_api_key(x_api_key=None)  # must not raise


@pytest.mark.anyio
async def test_missing_header_rejected(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "secret123")
    with pytest.raises(HTTPException) as exc:
        await require_api_key(x_api_key=None)
    assert exc.value.status_code == 401


@pytest.mark.anyio
async def test_wrong_key_rejected(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "secret123")
    with pytest.raises(HTTPException) as exc:
        await require_api_key(x_api_key="nope")
    assert exc.value.status_code == 401


@pytest.mark.anyio
async def test_correct_key_allowed(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "secret123")
    await require_api_key(x_api_key="secret123")  # must not raise


@pytest.fixture
def anyio_backend():
    return "asyncio"
```

**Step 3: Run to verify it fails**

Run: `python -m pytest backend/tests/test_auth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.security'`

**Step 4: Implement** — `backend/security.py`:

```python
from typing import Optional
from fastapi import Header, HTTPException

from backend.config import settings


async def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    """Static API-key gate for the single-curator system.

    When API_KEY is unset (local dev), all requests pass. When set, every
    request must carry a matching X-API-Key header.
    """
    if not settings.API_KEY:
        return
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
```

Add to `backend/config.py` `Settings` class (after `GROQ_API_KEY`):

```python
    API_KEY: Optional[str] = None
```

**Step 5: Run tests to verify pass**

Run: `python -m pytest backend/tests/test_auth.py -v`
Expected: 4 passed

**Step 6: Wire into `backend/main.py`**

Add import: `from fastapi import Depends` and `from backend.security import require_api_key`.
Add `dependencies=[Depends(require_api_key)]` to every `app.include_router(...)` call, e.g.:

```python
app.include_router(posts.router, prefix="/api/v1/posts", tags=["Posts"], dependencies=[Depends(require_api_key)])
```

(all 6 include_router calls). The directly-declared route also needs it:

```python
@app.get("/api/v1/posts/with-text", response_model=PaginatedPosts, dependencies=[Depends(require_api_key)])
```

`/health` untouched.

**Step 7: Smoke test** — with the venv active and `.env` present:

```bash
API_KEY=testkey uvicorn backend.main:app --port 5007 &
sleep 3
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5007/health                          # expect 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5007/api/v1/posts/                    # expect 401
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: testkey" http://localhost:5007/api/v1/posts/  # expect 200
kill %1
```

**Step 8: Commit**

```bash
git add backend/security.py backend/config.py backend/main.py backend/tests/
git commit -m "feat(backend): optional X-API-Key auth on all API routers"
```

**Deploy note (manual, later):** set `API_KEY` in the Render dashboard env vars.

---

## Task 2: Web frontend + Chrome extension send the key

**Files:**
- Modify: `frontend/src/config/api.js`
- Modify: `frontend/.env.example`
- Modify: `chrome-extension/content.js` (its fetch calls), `chrome-extension/popup.js`/`popup.html` (key entry)

**Step 1: Frontend** — in `frontend/src/config/api.js`, after the existing exports add:

```javascript
import axios from 'axios';

const API_KEY = import.meta.env.VITE_API_KEY;
if (API_KEY) {
  axios.defaults.headers.common['X-API-Key'] = API_KEY;
}
```

(Ensure this module is imported before any request — it already is, since every page imports `API_URL` from it. If any file uses `fetch` instead of axios, add the header there too — grep `fetch(` under `frontend/src` to check.)

Add `VITE_API_KEY=` to `frontend/.env.example`.

**Step 2: Extension** — in `chrome-extension/content.js`, find every `fetch(` call to the backend (grep `localhost:5007`). Create one helper near the top and route all backend fetches through it:

```javascript
async function apiFetch(path, options = {}) {
  const { apiKey } = await chrome.storage.sync.get('apiKey');
  options.headers = { ...(options.headers || {}), ...(apiKey ? { 'X-API-Key': apiKey } : {}) };
  return fetch(`${API_BASE}${path}`, options);
}
```

Add an API-key text input to `popup.html`/`popup.js` that saves to `chrome.storage.sync` (mirror however the popup already saves settings).

**Step 3: Verify** — run backend with `API_KEY=testkey`, run `npm run dev` in `frontend/` with `VITE_API_KEY=testkey` in `frontend/.env`, confirm the gallery loads; without the env var, confirm requests 401.

**Step 4: Commit**

```bash
git add frontend/src/config/api.js frontend/.env.example chrome-extension/
git commit -m "feat: send X-API-Key from web frontend and extension"
```

---

## Task 3: Android project scaffold

**Files (all new):**
- `android/settings.gradle.kts`, `android/build.gradle.kts`, `android/gradle.properties`, `android/gradle/libs.versions.toml`
- `android/app/build.gradle.kts`, `android/app/proguard-rules.pro`
- `android/app/src/main/AndroidManifest.xml`
- `android/app/src/main/java/com/semant/SemantApp.kt`
- `android/app/src/main/java/com/semant/MainActivity.kt`
- `android/app/src/main/res/values/strings.xml`, `res/values/themes.xml`
- Launcher icons: use Android Studio's Image Asset tool later; for now the default `ic_launcher` from a minimal adaptive icon (copy any AGP template, or temporarily set `android:icon="@android:drawable/sym_def_app_icon"`).
- Modify: `.gitignore` (add Android entries)

**Step 1: `.gitignore` additions**

```
# Android
android/.gradle/
android/build/
android/app/build/
android/local.properties
android/.idea/
```

**Step 2: `android/settings.gradle.kts`**

```kotlin
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "semant"
include(":app")
```

**Step 3: `android/gradle/libs.versions.toml`**

```toml
[versions]
agp = "8.7.3"
kotlin = "2.1.0"
ksp = "2.1.0-1.0.29"
composeBom = "2025.01.00"
activityCompose = "1.9.3"
navigationCompose = "2.8.5"
lifecycle = "2.8.7"
hilt = "2.54"
hiltNavigationCompose = "1.2.0"
hiltWork = "1.2.0"
retrofit = "2.11.0"
okhttp = "4.12.0"
kotlinxSerialization = "1.7.3"
retrofitSerialization = "2.11.0"
coil = "2.7.0"
room = "2.6.1"
work = "2.10.0"
paging = "3.3.5"
datastore = "1.1.1"
coreKtx = "1.15.0"
junit = "4.13.2"
robolectric = "4.14.1"
androidxTestCore = "1.6.1"
mockwebserver = "4.12.0"
coroutinesTest = "1.9.0"

[libraries]
androidx-core-ktx = { group = "androidx.core", name = "core-ktx", version.ref = "coreKtx" }
compose-bom = { group = "androidx.compose", name = "compose-bom", version.ref = "composeBom" }
compose-ui = { group = "androidx.compose.ui", name = "ui" }
compose-material3 = { group = "androidx.compose.material3", name = "material3" }
compose-ui-tooling-preview = { group = "androidx.compose.ui", name = "ui-tooling-preview" }
compose-ui-tooling = { group = "androidx.compose.ui", name = "ui-tooling" }
compose-material-icons = { group = "androidx.compose.material", name = "material-icons-extended" }
activity-compose = { group = "androidx.activity", name = "activity-compose", version.ref = "activityCompose" }
navigation-compose = { group = "androidx.navigation", name = "navigation-compose", version.ref = "navigationCompose" }
lifecycle-viewmodel-compose = { group = "androidx.lifecycle", name = "lifecycle-viewmodel-compose", version.ref = "lifecycle" }
lifecycle-runtime-compose = { group = "androidx.lifecycle", name = "lifecycle-runtime-compose", version.ref = "lifecycle" }
hilt-android = { group = "com.google.dagger", name = "hilt-android", version.ref = "hilt" }
hilt-compiler = { group = "com.google.dagger", name = "hilt-android-compiler", version.ref = "hilt" }
hilt-navigation-compose = { group = "androidx.hilt", name = "hilt-navigation-compose", version.ref = "hiltNavigationCompose" }
hilt-work = { group = "androidx.hilt", name = "hilt-work", version.ref = "hiltWork" }
hilt-work-compiler = { group = "androidx.hilt", name = "hilt-compiler", version.ref = "hiltWork" }
retrofit = { group = "com.squareup.retrofit2", name = "retrofit", version.ref = "retrofit" }
retrofit-kotlinx-serialization = { group = "com.squareup.retrofit2", name = "converter-kotlinx-serialization", version.ref = "retrofitSerialization" }
okhttp = { group = "com.squareup.okhttp3", name = "okhttp", version.ref = "okhttp" }
okhttp-logging = { group = "com.squareup.okhttp3", name = "logging-interceptor", version.ref = "okhttp" }
kotlinx-serialization-json = { group = "org.jetbrains.kotlinx", name = "kotlinx-serialization-json", version.ref = "kotlinxSerialization" }
coil-compose = { group = "io.coil-kt", name = "coil-compose", version.ref = "coil" }
room-runtime = { group = "androidx.room", name = "room-runtime", version.ref = "room" }
room-ktx = { group = "androidx.room", name = "room-ktx", version.ref = "room" }
room-compiler = { group = "androidx.room", name = "room-compiler", version.ref = "room" }
work-runtime = { group = "androidx.work", name = "work-runtime-ktx", version.ref = "work" }
work-testing = { group = "androidx.work", name = "work-testing", version.ref = "work" }
paging-runtime = { group = "androidx.paging", name = "paging-runtime-ktx", version.ref = "paging" }
paging-compose = { group = "androidx.paging", name = "paging-compose", version.ref = "paging" }
datastore-preferences = { group = "androidx.datastore", name = "datastore-preferences", version.ref = "datastore" }
junit = { group = "junit", name = "junit", version.ref = "junit" }
robolectric = { group = "org.robolectric", name = "robolectric", version.ref = "robolectric" }
androidx-test-core = { group = "androidx.test", name = "core-ktx", version.ref = "androidxTestCore" }
mockwebserver = { group = "com.squareup.okhttp3", name = "mockwebserver", version.ref = "mockwebserver" }
coroutines-test = { group = "org.jetbrains.kotlinx", name = "kotlinx-coroutines-test", version.ref = "coroutinesTest" }

[plugins]
android-application = { id = "com.android.application", version.ref = "agp" }
kotlin-android = { id = "org.jetbrains.kotlin.android", version.ref = "kotlin" }
kotlin-compose = { id = "org.jetbrains.kotlin.plugin.compose", version.ref = "kotlin" }
kotlin-serialization = { id = "org.jetbrains.kotlin.plugin.serialization", version.ref = "kotlin" }
ksp = { id = "com.google.devtools.ksp", version.ref = "ksp" }
hilt = { id = "com.google.dagger.hilt.android", version.ref = "hilt" }
```

**Step 4: `android/build.gradle.kts`** (root)

```kotlin
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    alias(libs.plugins.ksp) apply false
    alias(libs.plugins.hilt) apply false
}
```

**Step 5: `android/gradle.properties`**

```properties
org.gradle.jvmargs=-Xmx2048m
android.useAndroidX=true
kotlin.code.style=official
```

**Step 6: `android/app/build.gradle.kts`**

```kotlin
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.ksp)
    alias(libs.plugins.hilt)
}

android {
    namespace = "com.semant"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.semant"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }
    testOptions {
        unitTests { isIncludeAndroidResources = true }  // Robolectric
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.material3)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.material.icons)
    debugImplementation(libs.compose.ui.tooling)
    implementation(libs.activity.compose)
    implementation(libs.navigation.compose)
    implementation(libs.lifecycle.viewmodel.compose)
    implementation(libs.lifecycle.runtime.compose)

    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)
    implementation(libs.hilt.navigation.compose)
    implementation(libs.hilt.work)
    ksp(libs.hilt.work.compiler)

    implementation(libs.retrofit)
    implementation(libs.retrofit.kotlinx.serialization)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.coil.compose)

    implementation(libs.room.runtime)
    implementation(libs.room.ktx)
    ksp(libs.room.compiler)
    implementation(libs.work.runtime)
    implementation(libs.paging.runtime)
    implementation(libs.paging.compose)
    implementation(libs.datastore.preferences)

    testImplementation(libs.junit)
    testImplementation(libs.robolectric)
    testImplementation(libs.androidx.test.core)
    testImplementation(libs.mockwebserver)
    testImplementation(libs.coroutines.test)
    testImplementation(libs.work.testing)
}
```

**Step 7: `android/app/src/main/AndroidManifest.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />

    <application
        android:name=".SemantApp"
        android:label="@string/app_name"
        android:icon="@android:drawable/sym_def_app_icon"
        android:theme="@style/Theme.Semant"
        android:supportsRtl="true">

        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

        <!-- ShareActivity added in Task 8 -->
    </application>
</manifest>
```

**Step 8: `res/values/strings.xml` and `res/values/themes.xml`**

```xml
<resources>
    <string name="app_name">Semant</string>
</resources>
```

```xml
<resources>
    <style name="Theme.Semant" parent="android:Theme.Material.Light.NoActionBar" />
    <style name="Theme.Semant.Translucent" parent="Theme.Semant">
        <item name="android:windowIsTranslucent">true</item>
        <item name="android:windowBackground">@android:color/transparent</item>
        <item name="android:backgroundDimEnabled">false</item>
    </style>
</resources>
```

**Step 9: `SemantApp.kt` and `MainActivity.kt`**

```kotlin
package com.semant

import android.app.Application
import androidx.hilt.work.HiltWorkerFactory
import androidx.work.Configuration
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject

@HiltAndroidApp
class SemantApp : Application(), Configuration.Provider {
    @Inject lateinit var workerFactory: HiltWorkerFactory
    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder().setWorkerFactory(workerFactory).build()
}
```

```kotlin
package com.semant

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.Text
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { Text("Semant") }
    }
}
```

WorkManager on-demand init: because `SemantApp` implements `Configuration.Provider`, disable the default initializer by adding inside `<application>`:

```xml
<provider
    android:name="androidx.startup.InitializationProvider"
    android:authorities="${applicationId}.androidx-startup"
    android:exported="false"
    tools:node="merge">
    <meta-data
        android:name="androidx.work.WorkManagerInitializer"
        android:value="androidx.startup"
        tools:node="remove" />
</provider>
```

(add `xmlns:tools="http://schemas.android.com/tools"` to the manifest root).

**Step 10: Generate wrapper and build**

```bash
cd android && gradle wrapper --gradle-version 8.11.1
./gradlew assembleDebug
```

Expected: `BUILD SUCCESSFUL`, APK at `android/app/build/outputs/apk/debug/app-debug.apk`.

**Step 11: Commit**

```bash
git add android/ .gitignore
git commit -m "feat(android): project scaffold — Compose, Hilt, Room, WorkManager wiring"
```

---

## Task 4: Semant Compose theme

**Files:**
- Create: `android/app/src/main/java/com/semant/ui/theme/Color.kt`, `Type.kt`, `Theme.kt`

**Step 1: `Color.kt`** — values ported from `design-system/tokens.css`:

```kotlin
package com.semant.ui.theme

import androidx.compose.ui.graphics.Color

// Light — "Paper"
val PaperBg = Color(0xFFFBF9F5)
val PaperSurface = Color(0xFFFFFFFF)
val PaperSurface2 = Color(0xFFF4F1EA)
val PaperInk = Color(0xFF1A1814)
val PaperInkMuted = Color(0xFF6F6A61)
val PaperLine = Color(0xFFE7E2D8)
val Terracotta = Color(0xFFC4533A)
val TerracottaDeep = Color(0xFFA53F2A)
val TerracottaSoft = Color(0xFFF7E8E2)

// Dark — "Ink"
val InkBg = Color(0xFF14120E)
val InkSurface = Color(0xFF1C1A15)
val InkSurface2 = Color(0xFF24211B)
val InkText = Color(0xFFF3EFE6)
val InkTextMuted = Color(0xFFA8A294)
val InkLine = Color(0xFF322E26)
val TerracottaDark = Color(0xFFD2654A)
val TerracottaDeepDark = Color(0xFFB84E33)
val TerracottaSoftDark = Color(0xFF2E211B)
```

**Step 2: `Theme.kt`**

```kotlin
package com.semant.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val LightColors = lightColorScheme(
    primary = Terracotta,
    onPrimary = PaperSurface,
    primaryContainer = TerracottaSoft,
    onPrimaryContainer = TerracottaDeep,
    background = PaperBg,
    onBackground = PaperInk,
    surface = PaperSurface,
    onSurface = PaperInk,
    surfaceVariant = PaperSurface2,
    onSurfaceVariant = PaperInkMuted,
    outline = PaperLine,
)

private val DarkColors = darkColorScheme(
    primary = TerracottaDark,
    onPrimary = InkBg,
    primaryContainer = TerracottaSoftDark,
    onPrimaryContainer = TerracottaDark,
    background = InkBg,
    onBackground = InkText,
    surface = InkSurface,
    onSurface = InkText,
    surfaceVariant = InkSurface2,
    onSurfaceVariant = InkTextMuted,
    outline = InkLine,
)

@Composable
fun SemantTheme(darkTheme: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        typography = SemantTypography,
        content = content,
    )
}
```

**Step 3: `Type.kt`** — Fraunces (display) + Inter (body). Download `Fraunces-Medium.ttf`, `Fraunces-SemiBold.ttf`, `Inter-Regular.ttf`, `Inter-Medium.ttf`, `Inter-SemiBold.ttf` from Google Fonts into `android/app/src/main/res/font/` (lowercase_underscore filenames: `fraunces_medium.ttf` etc.). If download isn't possible in the session, use `FontFamily.Serif` / `FontFamily.SansSerif` and leave a `// TODO: bundle Fraunces/Inter` — do not block on fonts.

```kotlin
package com.semant.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import com.semant.R

val Fraunces = FontFamily(
    Font(R.font.fraunces_medium, FontWeight.Medium),
    Font(R.font.fraunces_semibold, FontWeight.SemiBold),
)
val Inter = FontFamily(
    Font(R.font.inter_regular, FontWeight.Normal),
    Font(R.font.inter_medium, FontWeight.Medium),
    Font(R.font.inter_semibold, FontWeight.SemiBold),
)

val SemantTypography = Typography(
    displaySmall = TextStyle(fontFamily = Fraunces, fontWeight = FontWeight.Medium, fontSize = 36.sp, letterSpacing = (-0.5).sp),
    headlineMedium = TextStyle(fontFamily = Fraunces, fontWeight = FontWeight.Medium, fontSize = 28.sp, letterSpacing = (-0.4).sp),
    titleLarge = TextStyle(fontFamily = Fraunces, fontWeight = FontWeight.Medium, fontSize = 22.sp),
    titleMedium = TextStyle(fontFamily = Inter, fontWeight = FontWeight.SemiBold, fontSize = 16.sp),
    bodyLarge = TextStyle(fontFamily = Inter, fontSize = 16.sp, lineHeight = 26.sp),
    bodyMedium = TextStyle(fontFamily = Inter, fontSize = 14.sp, lineHeight = 22.sp),
    labelLarge = TextStyle(fontFamily = Inter, fontWeight = FontWeight.SemiBold, fontSize = 14.sp),
    labelSmall = TextStyle(fontFamily = Inter, fontWeight = FontWeight.SemiBold, fontSize = 11.sp, letterSpacing = 1.2.sp),
)
```

**Step 4:** Wrap `MainActivity` content in `SemantTheme { ... }`. Build: `./gradlew assembleDebug` → BUILD SUCCESSFUL.

**Step 5: Commit** — `git commit -m "feat(android): Semant paper/ink/terracotta Compose theme"`

---

## Task 5: Settings + networking core (TDD)

**Files:**
- Create: `data/SettingsRepository.kt`, `data/remote/Dtos.kt`, `data/remote/SemantApi.kt`, `data/remote/Interceptors.kt`, `data/di/AppModule.kt`, `data/PostRepository.kt`
- Test: `android/app/src/test/java/com/semant/data/PostRepositoryTest.kt`

**Step 1: `data/SettingsRepository.kt`**

```kotlin
package com.semant.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.runBlocking
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore by preferencesDataStore(name = "settings")

@Singleton
class SettingsRepository @Inject constructor(@ApplicationContext private val context: Context) {
    private val BASE_URL = stringPreferencesKey("base_url")
    private val API_KEY = stringPreferencesKey("api_key")

    companion object { const val DEFAULT_BASE_URL = "https://sharirasutra.onrender.com" }

    val baseUrl: Flow<String> = context.dataStore.data.map { it[BASE_URL] ?: DEFAULT_BASE_URL }
    val apiKey: Flow<String> = context.dataStore.data.map { it[API_KEY] ?: "" }

    // Called from OkHttp interceptors on IO threads; DataStore read is fast.
    fun baseUrlBlocking(): String = runBlocking { baseUrl.first() }
    fun apiKeyBlocking(): String = runBlocking { apiKey.first() }

    suspend fun setBaseUrl(value: String) = context.dataStore.edit { it[BASE_URL] = value.trimEnd('/') }
    suspend fun setApiKey(value: String) = context.dataStore.edit { it[API_KEY] = value.trim() }
}
```

**Step 2: `data/remote/Dtos.kt`**

```kotlin
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
```

**Step 3: `data/remote/SemantApi.kt`**

```kotlin
package com.semant.data.remote

import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.http.*

interface SemantApi {
    @GET("api/v1/posts/")
    suspend fun getPosts(
        @Query("page") page: Int,
        @Query("limit") limit: Int = 30,
        @Query("tag") tag: String? = null,
    ): PaginatedPostsDto

    @GET("api/v1/posts/{id}")
    suspend fun getPost(@Path("id") id: String): PostDto

    @GET("api/v1/posts/tags/")
    suspend fun getTags(): List<String>

    @Multipart
    @POST("api/v1/posts/")
    suspend fun uploadImage(
        @Part file: MultipartBody.Part,
        @Part("general_tags_str") generalTagsStr: RequestBody?,
    ): PostDto

    @POST("api/v1/posts/upload-from-url")
    suspend fun uploadFromUrl(@Body body: UrlUploadRequestDto): PostDto
}
```

**Step 4: `data/remote/Interceptors.kt`** — dynamic base URL + API key:

```kotlin
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
```

**Step 5: `data/di/AppModule.kt`**

```kotlin
package com.semant.data.di

import com.semant.data.remote.ApiKeyInterceptor
import com.semant.data.remote.BaseUrlInterceptor
import com.semant.data.remote.SemantApi
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.kotlinxserialization.asConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {
    @Provides @Singleton
    fun provideJson(): Json = Json { ignoreUnknownKeys = true; coerceInputValues = true }

    @Provides @Singleton
    fun provideOkHttp(baseUrl: BaseUrlInterceptor, apiKey: ApiKeyInterceptor): OkHttpClient =
        OkHttpClient.Builder()
            .addInterceptor(baseUrl)
            .addInterceptor(apiKey)
            .connectTimeout(20, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .writeTimeout(120, TimeUnit.SECONDS)
            .build()

    @Provides @Singleton
    fun provideApi(client: OkHttpClient, json: Json): SemantApi =
        Retrofit.Builder()
            .baseUrl("http://localhost/") // always rewritten by BaseUrlInterceptor
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(SemantApi::class.java)
}
```

**Step 6: `data/PostRepository.kt`**

```kotlin
package com.semant.data

import com.semant.data.remote.PaginatedPostsDto
import com.semant.data.remote.PostDto
import com.semant.data.remote.SemantApi
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class PostRepository @Inject constructor(private val api: SemantApi) {
    suspend fun getPosts(page: Int, tag: String? = null): PaginatedPostsDto = api.getPosts(page = page, tag = tag)
    suspend fun getPost(id: String): PostDto = api.getPost(id)
    suspend fun getTags(): List<String> = api.getTags()
}
```

**Step 7: Write the failing test** — `app/src/test/java/com/semant/data/PostRepositoryTest.kt`. Plain JVM test (no Robolectric needed): build the Retrofit stack by hand against MockWebServer.

```kotlin
package com.semant.data

import com.semant.data.remote.SemantApi
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.kotlinxserialization.asConverterFactory

class PostRepositoryTest {
    private lateinit var server: MockWebServer
    private lateinit var repo: PostRepository

    @Before fun setUp() {
        server = MockWebServer().apply { start() }
        val json = Json { ignoreUnknownKeys = true; coerceInputValues = true }
        val api = Retrofit.Builder()
            .baseUrl(server.url("/"))
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(SemantApi::class.java)
        repo = PostRepository(api)
    }

    @After fun tearDown() = server.shutdown()

    @Test fun `parses paginated posts and ignores unknown fields`() = runTest {
        server.enqueue(MockResponse().setBody(
            """{"posts":[{"id":"abc","photo_url":"https://x/y.jpg","photo_public_id":"posts/1",
                "general_tags":["saree"],"unknown_field":42}],
                "total_pages":3,"current_page":1}"""
        ).addHeader("Content-Type", "application/json"))

        val page = repo.getPosts(page = 1)

        assertEquals(1, page.posts.size)
        assertEquals("abc", page.posts[0].id)
        assertEquals(listOf("saree"), page.posts[0].generalTags)
        assertEquals(3, page.totalPages)
        val recorded = server.takeRequest()
        assertEquals("/api/v1/posts/?page=1&limit=30", recorded.path)
    }
}
```

**Step 8: Run** — `cd android && ./gradlew :app:testDebugUnitTest --tests '*PostRepositoryTest*'`
Expected first run: compile errors until all files from Steps 1–6 exist; then PASS.

**Step 9: Full build** — `./gradlew assembleDebug testDebugUnitTest` → BUILD SUCCESSFUL.

**Step 10: Commit** — `git commit -m "feat(android): settings store, Retrofit API client with dynamic base URL + API key"`

---

## Task 6: Room capture queue (TDD)

**Files:**
- Create: `data/local/QueuedCapture.kt`, `data/local/CaptureDao.kt`, `data/local/SemantDatabase.kt`; extend `data/di/AppModule.kt`
- Test: `app/src/test/java/com/semant/data/local/CaptureDaoTest.kt` (Robolectric)

**Step 1: Entity + status enum** — `data/local/QueuedCapture.kt`:

```kotlin
package com.semant.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

enum class CaptureStatus { PENDING, UPLOADING, FAILED, DONE }

@Entity(tableName = "queued_captures")
data class QueuedCapture(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val localFilePath: String? = null,   // set for shared image bytes
    val sourceUrl: String? = null,       // set for shared URLs (Chrome)
    val tags: String = "",               // comma-separated
    val note: String = "",
    val status: CaptureStatus = CaptureStatus.PENDING,
    val attemptCount: Int = 0,
    val lastError: String? = null,
    val createdAt: Long,
)
```

**Step 2: DAO** — `data/local/CaptureDao.kt`:

```kotlin
package com.semant.data.local

import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Dao
interface CaptureDao {
    @Insert suspend fun insert(capture: QueuedCapture): Long
    @Update suspend fun update(capture: QueuedCapture)
    @Query("SELECT * FROM queued_captures WHERE id = :id") suspend fun byId(id: Long): QueuedCapture?
    @Query("SELECT * FROM queued_captures ORDER BY createdAt DESC") fun observeAll(): Flow<List<QueuedCapture>>
    @Query("SELECT COUNT(*) FROM queued_captures WHERE status IN ('PENDING','UPLOADING','FAILED')")
    fun observeActiveCount(): Flow<Int>
    @Query("DELETE FROM queued_captures WHERE id = :id") suspend fun delete(id: Long)
    @Query("DELETE FROM queued_captures WHERE status = 'DONE' AND createdAt < :olderThan")
    suspend fun pruneDone(olderThan: Long)
}
```

**Step 3: Database + Hilt provider** — `data/local/SemantDatabase.kt`:

```kotlin
package com.semant.data.local

import androidx.room.Database
import androidx.room.RoomDatabase

@Database(entities = [QueuedCapture::class], version = 1, exportSchema = false)
abstract class SemantDatabase : RoomDatabase() {
    abstract fun captureDao(): CaptureDao
}
```

Add to `AppModule`:

```kotlin
@Provides @Singleton
fun provideDb(@ApplicationContext context: Context): SemantDatabase =
    Room.databaseBuilder(context, SemantDatabase::class.java, "semant.db").build()

@Provides
fun provideCaptureDao(db: SemantDatabase): CaptureDao = db.captureDao()
```

(imports: `android.content.Context`, `androidx.room.Room`, `dagger.hilt.android.qualifiers.ApplicationContext`, `com.semant.data.local.*`)

**Step 4: Write the failing test** — `CaptureDaoTest.kt`:

```kotlin
package com.semant.data.local

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class CaptureDaoTest {
    private lateinit var db: SemantDatabase
    private lateinit var dao: CaptureDao

    @Before fun setUp() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        db = Room.inMemoryDatabaseBuilder(context, SemantDatabase::class.java).build()
        dao = db.captureDao()
    }

    @After fun tearDown() = db.close()

    @Test fun `insert and observe pending captures`() = runTest {
        val id = dao.insert(QueuedCapture(localFilePath = "/x/a.jpg", tags = "saree", createdAt = 1000L))
        val all = dao.observeAll().first()
        assertEquals(1, all.size)
        assertEquals(CaptureStatus.PENDING, all[0].status)
        assertEquals(1, dao.observeActiveCount().first())

        dao.update(all[0].copy(status = CaptureStatus.DONE))
        assertEquals(0, dao.observeActiveCount().first())
        dao.delete(id)
        assertEquals(0, dao.observeAll().first().size)
    }
}
```

**Step 5: Run** — `./gradlew :app:testDebugUnitTest --tests '*CaptureDaoTest*'` → PASS (after implementation compiles).

**Step 6: Commit** — `git commit -m "feat(android): Room capture queue (entity, dao, db)"`

---

## Task 7: CaptureRepository + UploadWorker (TDD)

**Files:**
- Create: `capture/CaptureRepository.kt`, `capture/UploadWorker.kt`, `capture/UploadNotifier.kt`
- Test: `app/src/test/java/com/semant/capture/UploadWorkerTest.kt`

**Step 1: `capture/CaptureRepository.kt`**

```kotlin
package com.semant.capture

import android.content.Context
import android.net.Uri
import androidx.work.*
import com.semant.data.local.CaptureDao
import com.semant.data.local.CaptureStatus
import com.semant.data.local.QueuedCapture
import dagger.hilt.android.qualifiers.ApplicationContext
import java.io.File
import java.util.UUID
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class CaptureRepository @Inject constructor(
    @ApplicationContext private val context: Context,
    private val dao: CaptureDao,
) {
    /** Copy shared bytes into app-private storage (content URIs die with the sender). */
    fun copyToLocal(uri: Uri): File {
        val dir = File(context.filesDir, "captures").apply { mkdirs() }
        val dest = File(dir, "${UUID.randomUUID()}.img")
        context.contentResolver.openInputStream(uri).use { input ->
            requireNotNull(input) { "Cannot read shared content" }
            dest.outputStream().use { input.copyTo(it) }
        }
        require(dest.length() in 1..MAX_BYTES) { "Image is empty or larger than 25MB" }
        return dest
    }

    suspend fun enqueueImage(uri: Uri, tags: String, note: String, now: Long = System.currentTimeMillis()): Long {
        val file = copyToLocal(uri)
        val id = dao.insert(QueuedCapture(localFilePath = file.absolutePath, tags = tags, note = note, createdAt = now))
        scheduleUpload(id)
        return id
    }

    suspend fun enqueueUrl(url: String, tags: String, note: String, now: Long = System.currentTimeMillis()): Long {
        val id = dao.insert(QueuedCapture(sourceUrl = url, tags = tags, note = note, createdAt = now))
        scheduleUpload(id)
        return id
    }

    suspend fun retry(id: Long) {
        dao.byId(id)?.let { dao.update(it.copy(status = CaptureStatus.PENDING, attemptCount = 0, lastError = null)) }
        scheduleUpload(id)
    }

    suspend fun remove(capture: QueuedCapture) {
        capture.localFilePath?.let { File(it).delete() }
        dao.delete(capture.id)
    }

    fun scheduleUpload(id: Long) {
        val request = OneTimeWorkRequestBuilder<UploadWorker>()
            .setInputData(workDataOf(UploadWorker.KEY_CAPTURE_ID to id))
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork("upload-$id", ExistingWorkPolicy.KEEP, request)
    }

    companion object { const val MAX_BYTES = 25L * 1024 * 1024 }
}
```

**Step 2: `capture/UploadWorker.kt`**

```kotlin
package com.semant.capture

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.semant.data.local.CaptureDao
import com.semant.data.local.CaptureStatus
import com.semant.data.remote.SemantApi
import com.semant.data.remote.UrlUploadRequestDto
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.HttpException
import java.io.File

@HiltWorker
class UploadWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val dao: CaptureDao,
    private val api: SemantApi,
    private val notifier: UploadNotifier,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val id = inputData.getLong(KEY_CAPTURE_ID, -1)
        val capture = dao.byId(id) ?: return Result.success()
        if (capture.status == CaptureStatus.DONE) return Result.success()

        dao.update(capture.copy(status = CaptureStatus.UPLOADING, attemptCount = capture.attemptCount + 1))
        return try {
            if (capture.sourceUrl != null) {
                api.uploadFromUrl(UrlUploadRequestDto(
                    imageUrl = capture.sourceUrl,
                    generalTags = capture.tags.split(',').map { it.trim() }.filter { it.isNotEmpty() },
                ))
            } else {
                val file = File(requireNotNull(capture.localFilePath))
                val part = MultipartBody.Part.createFormData(
                    "file", "capture.jpg", file.asRequestBody("image/*".toMediaType()))
                val tagsBody = capture.tags.takeIf { it.isNotBlank() }?.toRequestBody("text/plain".toMediaType())
                api.uploadImage(part, tagsBody)
                file.delete()
            }
            dao.update(requireNotNull(dao.byId(id)).copy(status = CaptureStatus.DONE, lastError = null))
            Result.success()
        } catch (e: Exception) {
            val permanent = e is HttpException && e.code() in 400..499 && e.code() != 429
            val giveUp = permanent || runAttemptCount >= MAX_ATTEMPTS
            dao.update(requireNotNull(dao.byId(id)).copy(
                status = if (giveUp) CaptureStatus.FAILED else CaptureStatus.PENDING,
                lastError = e.message ?: e.javaClass.simpleName,
            ))
            if (giveUp) { notifier.notifyFailure(id); Result.failure() } else Result.retry()
        }
    }

    companion object {
        const val KEY_CAPTURE_ID = "capture_id"
        const val MAX_ATTEMPTS = 5
    }
}
```

**Step 3: `capture/UploadNotifier.kt`**

```kotlin
package com.semant.capture

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import com.semant.MainActivity
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class UploadNotifier @Inject constructor(@ApplicationContext private val context: Context) {
    private val manager = context.getSystemService(NotificationManager::class.java)

    init {
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL, "Uploads", NotificationManager.IMPORTANCE_DEFAULT))
    }

    fun notifyFailure(captureId: Long) {
        val intent = Intent(context, MainActivity::class.java).putExtra("open_queue", true)
        val pending = PendingIntent.getActivity(context, captureId.toInt(), intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        runCatching {
            manager.notify(captureId.toInt(), NotificationCompat.Builder(context, CHANNEL)
                .setSmallIcon(android.R.drawable.stat_sys_warning)
                .setContentTitle("Semant upload failed")
                .setContentText("A captured image could not be uploaded. Tap to review.")
                .setContentIntent(pending)
                .setAutoCancel(true)
                .build())
        } // no POST_NOTIFICATIONS permission → silently skip; Queue screen still shows it
    }

    companion object { const val CHANNEL = "uploads" }
}
```

**Step 4: Write the failing worker test** — `UploadWorkerTest.kt` (Robolectric + MockWebServer + `TestListenableWorkerBuilder`). Test three behaviors:

```kotlin
package com.semant.capture

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.work.ListenableWorker.Result
import androidx.work.testing.TestListenableWorkerBuilder
import androidx.work.WorkerFactory
import androidx.work.WorkerParameters
import com.semant.data.local.CaptureStatus
import com.semant.data.local.QueuedCapture
import com.semant.data.local.SemantDatabase
import com.semant.data.remote.SemantApi
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import retrofit2.Retrofit
import retrofit2.converter.kotlinxserialization.asConverterFactory
import java.io.File

@RunWith(RobolectricTestRunner::class)
class UploadWorkerTest {
    private lateinit var context: Context
    private lateinit var server: MockWebServer
    private lateinit var db: SemantDatabase
    private lateinit var api: SemantApi
    private lateinit var notifier: UploadNotifier

    private val postJson = """{"id":"p1","photo_url":"https://x/y.jpg","photo_public_id":"posts/1"}"""

    @Before fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        server = MockWebServer().apply { start() }
        db = Room.inMemoryDatabaseBuilder(context, SemantDatabase::class.java).build()
        val json = Json { ignoreUnknownKeys = true; coerceInputValues = true }
        api = Retrofit.Builder().baseUrl(server.url("/"))
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build().create(SemantApi::class.java)
        notifier = UploadNotifier(context)
    }

    @After fun tearDown() { server.shutdown(); db.close() }

    private fun buildWorker(captureId: Long): UploadWorker =
        TestListenableWorkerBuilder<UploadWorker>(context)
            .setInputData(androidx.work.workDataOf(UploadWorker.KEY_CAPTURE_ID to captureId))
            .setWorkerFactory(object : WorkerFactory() {
                override fun createWorker(c: Context, cls: String, p: WorkerParameters) =
                    UploadWorker(c, p, db.captureDao(), api, notifier)
            }).build() as UploadWorker

    @Test fun `file upload success marks DONE and deletes local file`() = runTest {
        server.enqueue(MockResponse().setResponseCode(201).setBody(postJson)
            .addHeader("Content-Type", "application/json"))
        val file = File(context.filesDir, "t.img").apply { writeBytes(byteArrayOf(1, 2, 3)) }
        val id = db.captureDao().insert(QueuedCapture(localFilePath = file.absolutePath, tags = "saree", createdAt = 1L))

        val result = buildWorker(id).doWork()

        assertEquals(Result.success(), result)
        assertEquals(CaptureStatus.DONE, db.captureDao().byId(id)!!.status)
        assertTrue(!file.exists())
        assertTrue(server.takeRequest().headers["Content-Type"]!!.startsWith("multipart/"))
    }

    @Test fun `url upload hits upload-from-url`() = runTest {
        server.enqueue(MockResponse().setResponseCode(201).setBody(postJson)
            .addHeader("Content-Type", "application/json"))
        val id = db.captureDao().insert(QueuedCapture(sourceUrl = "https://img.example/a.jpg", tags = "", createdAt = 1L))

        val result = buildWorker(id).doWork()

        assertEquals(Result.success(), result)
        assertEquals("/api/v1/posts/upload-from-url", server.takeRequest().path)
    }

    @Test fun `server 500 retries and keeps PENDING`() = runTest {
        server.enqueue(MockResponse().setResponseCode(500))
        val file = File(context.filesDir, "t2.img").apply { writeBytes(byteArrayOf(1)) }
        val id = db.captureDao().insert(QueuedCapture(localFilePath = file.absolutePath, createdAt = 1L))

        val result = buildWorker(id).doWork()

        assertEquals(Result.retry(), result)
        assertEquals(CaptureStatus.PENDING, db.captureDao().byId(id)!!.status)
        assertTrue(file.exists())  // kept for retry
    }

    @Test fun `client 4xx fails permanently`() = runTest {
        server.enqueue(MockResponse().setResponseCode(422).setBody("bad"))
        val id = db.captureDao().insert(QueuedCapture(sourceUrl = "https://img.example/a.jpg", createdAt = 1L))

        val result = buildWorker(id).doWork()

        assertEquals(Result.failure(), result)
        assertEquals(CaptureStatus.FAILED, db.captureDao().byId(id)!!.status)
    }
}
```

**Step 5: Run** — `./gradlew :app:testDebugUnitTest --tests '*UploadWorkerTest*'` → 4 passed.
Note: Retrofit suspend + MockWebServer + Robolectric can need `@Config(sdk = [34])` if Robolectric lacks SDK 35 shadows — add if the runner complains.

**Step 6: Commit** — `git commit -m "feat(android): capture repository and WorkManager upload worker"`

---

## Task 8: ShareActivity + capture sheet

**Files:**
- Create: `capture/ShareActivity.kt`, `capture/ShareViewModel.kt`
- Modify: `AndroidManifest.xml`

**Step 1: Manifest** — inside `<application>`:

```xml
<activity
    android:name=".capture.ShareActivity"
    android:exported="true"
    android:excludeFromRecents="true"
    android:taskAffinity=""
    android:theme="@style/Theme.Semant.Translucent"
    android:label="Save to Semant">
    <intent-filter>
        <action android:name="android.intent.action.SEND" />
        <category android:name="android.intent.category.DEFAULT" />
        <data android:mimeType="image/*" />
    </intent-filter>
    <intent-filter>
        <action android:name="android.intent.action.SEND" />
        <category android:name="android.intent.category.DEFAULT" />
        <data android:mimeType="text/plain" />
    </intent-filter>
    <intent-filter>
        <action android:name="android.intent.action.SEND_MULTIPLE" />
        <category android:name="android.intent.category.DEFAULT" />
        <data android:mimeType="image/*" />
    </intent-filter>
</activity>
```

**Step 2: `capture/ShareViewModel.kt`**

```kotlin
package com.semant.capture

import android.content.Intent
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.semant.data.PostRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

sealed interface SharePayload {
    data class Images(val uris: List<Uri>) : SharePayload
    data class Link(val url: String) : SharePayload
    data object Invalid : SharePayload
}

data class ShareUiState(
    val payload: SharePayload = SharePayload.Invalid,
    val tags: String = "",
    val note: String = "",
    val knownTags: List<String> = emptyList(),
    val saving: Boolean = false,
    val done: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class ShareViewModel @Inject constructor(
    private val captures: CaptureRepository,
    private val posts: PostRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(ShareUiState())
    val state: StateFlow<ShareUiState> = _state

    fun init(intent: Intent) {
        _state.value = _state.value.copy(payload = parse(intent))
        viewModelScope.launch {
            runCatching { posts.getTags() }.onSuccess {
                _state.value = _state.value.copy(knownTags = it.filterNotNull())
            } // offline is fine — autocomplete is a nicety
        }
    }

    fun setTags(v: String) { _state.value = _state.value.copy(tags = v) }
    fun setNote(v: String) { _state.value = _state.value.copy(note = v) }

    fun save() {
        val s = _state.value
        _state.value = s.copy(saving = true)
        viewModelScope.launch {
            runCatching {
                when (val p = s.payload) {
                    is SharePayload.Images -> p.uris.forEach { captures.enqueueImage(it, s.tags, s.note) }
                    is SharePayload.Link -> captures.enqueueUrl(p.url, s.tags, s.note)
                    SharePayload.Invalid -> error("Nothing shareable found")
                }
            }.onSuccess { _state.value = _state.value.copy(saving = false, done = true) }
             .onFailure { _state.value = _state.value.copy(saving = false, error = it.message) }
        }
    }

    private fun parse(intent: Intent): SharePayload = when (intent.action) {
        Intent.ACTION_SEND -> {
            @Suppress("DEPRECATION")
            val uri = intent.getParcelableExtra<Uri>(Intent.EXTRA_STREAM)
            val text = intent.getStringExtra(Intent.EXTRA_TEXT)
            when {
                uri != null -> SharePayload.Images(listOf(uri))
                text != null -> URL_REGEX.find(text)?.let { SharePayload.Link(it.value) } ?: SharePayload.Invalid
                else -> SharePayload.Invalid
            }
        }
        Intent.ACTION_SEND_MULTIPLE -> {
            @Suppress("DEPRECATION")
            val uris = intent.getParcelableArrayListExtra<Uri>(Intent.EXTRA_STREAM).orEmpty()
            if (uris.isEmpty()) SharePayload.Invalid else SharePayload.Images(uris)
        }
        else -> SharePayload.Invalid
    }

    companion object { val URL_REGEX = Regex("""https?://\S+""") }
}
```

**Step 3: `capture/ShareActivity.kt`**

```kotlin
package com.semant.capture

import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.semant.ui.theme.SemantTheme
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class ShareActivity : ComponentActivity() {
    private val viewModel: ShareViewModel by viewModels()

    @OptIn(ExperimentalMaterial3Api::class)
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        viewModel.init(intent)

        setContent {
            SemantTheme {
                val state by viewModel.state.collectAsState()
                val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

                LaunchedEffect(state.done, state.error) {
                    if (state.done) {
                        Toast.makeText(this@ShareActivity, "Saved to Semant queue", Toast.LENGTH_SHORT).show()
                        finish()
                    }
                    state.error?.let {
                        Toast.makeText(this@ShareActivity, it, Toast.LENGTH_LONG).show()
                        if (state.payload == SharePayload.Invalid) finish()
                    }
                }

                ModalBottomSheet(onDismissRequest = { finish() }, sheetState = sheetState) {
                    Column(Modifier.padding(horizontal = 20.dp).padding(bottom = 32.dp)) {
                        Text("Save to Semant", style = MaterialTheme.typography.titleLarge)
                        Spacer(Modifier.height(12.dp))

                        when (val p = state.payload) {
                            is SharePayload.Images -> LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                items(p.uris) { uri ->
                                    AsyncImage(model = uri, contentDescription = null,
                                        modifier = Modifier.size(96.dp), contentScale = ContentScale.Crop)
                                }
                            }
                            is SharePayload.Link -> Text(p.url, style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2)
                            SharePayload.Invalid -> Text("Nothing shareable found")
                        }

                        Spacer(Modifier.height(16.dp))
                        OutlinedTextField(value = state.tags, onValueChange = viewModel::setTags,
                            label = { Text("Tags (comma-separated)") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                        if (state.knownTags.isNotEmpty()) {
                            Spacer(Modifier.height(8.dp))
                            LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                items(state.knownTags.take(20)) { tag ->
                                    SuggestionChip(onClick = {
                                        val cur = state.tags.split(',').map { it.trim() }.filter { it.isNotEmpty() }
                                        if (tag !in cur) viewModel.setTags((cur + tag).joinToString(", "))
                                    }, label = { Text(tag) })
                                }
                            }
                        }
                        Spacer(Modifier.height(8.dp))
                        OutlinedTextField(value = state.note, onValueChange = viewModel::setNote,
                            label = { Text("Note (optional)") }, modifier = Modifier.fillMaxWidth())
                        Spacer(Modifier.height(16.dp))
                        Button(onClick = viewModel::save, enabled = !state.saving && state.payload != SharePayload.Invalid,
                            modifier = Modifier.fillMaxWidth()) {
                            Text(if (state.saving) "Saving…" else "Save")
                        }
                    }
                }
            }
        }
    }
}
```

**Step 4: Build + manual verify** — `./gradlew installDebug` on a connected device (or emulator: `adb install app/build/outputs/apk/debug/app-debug.apk`). Share an image from the Photos/Files app → Semant appears in the share sheet → sheet opens → Save → toast. Check the row exists: `adb shell run-as com.semant ls files/captures`.

**Step 5: Commit** — `git commit -m "feat(android): ShareActivity — share-sheet capture into offline queue"`

---

## Task 9: Gallery screen (Paging 3)

**Files:**
- Create: `gallery/PostPagingSource.kt`, `gallery/GalleryViewModel.kt`, `gallery/GalleryScreen.kt`

**Step 1: `gallery/PostPagingSource.kt`**

```kotlin
package com.semant.gallery

import androidx.paging.PagingSource
import androidx.paging.PagingState
import com.semant.data.PostRepository
import com.semant.data.remote.PostDto

class PostPagingSource(
    private val repo: PostRepository,
    private val tag: String?,
) : PagingSource<Int, PostDto>() {
    override suspend fun load(params: LoadParams<Int>): LoadResult<Int, PostDto> = try {
        val page = params.key ?: 1
        val result = repo.getPosts(page = page, tag = tag)
        LoadResult.Page(
            data = result.posts,
            prevKey = if (page > 1) page - 1 else null,
            nextKey = if (page < result.totalPages) page + 1 else null,
        )
    } catch (e: Exception) {
        LoadResult.Error(e)
    }

    override fun getRefreshKey(state: PagingState<Int, PostDto>): Int? =
        state.anchorPosition?.let { state.closestPageToPosition(it)?.prevKey?.plus(1) ?: 1 }
}
```

**Step 2: `gallery/GalleryViewModel.kt`**

```kotlin
package com.semant.gallery

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.paging.Pager
import androidx.paging.PagingConfig
import androidx.paging.cachedIn
import com.semant.data.PostRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

@OptIn(ExperimentalCoroutinesApi::class)
@HiltViewModel
class GalleryViewModel @Inject constructor(private val repo: PostRepository) : ViewModel() {
    private val _selectedTag = MutableStateFlow<String?>(null)
    val selectedTag: StateFlow<String?> = _selectedTag

    private val _tags = MutableStateFlow<List<String>>(emptyList())
    val tags: StateFlow<List<String>> = _tags

    val posts = _selectedTag.flatMapLatest { tag ->
        Pager(PagingConfig(pageSize = 30, initialLoadSize = 30)) { PostPagingSource(repo, tag) }.flow
    }.cachedIn(viewModelScope)

    init {
        viewModelScope.launch { runCatching { repo.getTags() }.onSuccess { _tags.value = it.filterNotNull() } }
    }

    fun selectTag(tag: String?) { _selectedTag.value = tag }
}
```

**Step 3: `gallery/GalleryScreen.kt`**

```kotlin
package com.semant.gallery

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.paging.LoadState
import androidx.paging.compose.collectAsLazyPagingItems
import androidx.paging.compose.itemKey
import coil.compose.AsyncImage
import com.semant.data.remote.PostDto

@Composable
fun GalleryScreen(
    onOpenPost: (String) -> Unit,
    viewModel: GalleryViewModel = hiltViewModel(),
) {
    val posts = viewModel.posts.collectAsLazyPagingItems()
    val tags by viewModel.tags.collectAsState()
    val selected by viewModel.selectedTag.collectAsState()

    Column(Modifier.fillMaxSize()) {
        Text("Gallery", style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.padding(start = 20.dp, top = 16.dp, bottom = 8.dp))

        if (tags.isNotEmpty()) {
            LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp),
                contentPadding = PaddingValues(horizontal = 20.dp)) {
                items(tags) { tag ->
                    FilterChip(selected = tag == selected,
                        onClick = { viewModel.selectTag(if (tag == selected) null else tag) },
                        label = { Text(tag) })
                }
            }
        }

        when (posts.loadState.refresh) {
            is LoadState.Error -> Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center) {
                Text("Couldn't reach Semant", style = MaterialTheme.typography.titleMedium)
                Text("Check the base URL and API key in Settings",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(12.dp))
                Button(onClick = { posts.retry() }) { Text("Retry") }
            }
            is LoadState.Loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            else -> LazyVerticalGrid(
                columns = GridCells.Adaptive(minSize = 110.dp),
                contentPadding = PaddingValues(12.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                items(count = posts.itemCount, key = posts.itemKey { it.id }) { index ->
                    posts[index]?.let { post: PostDto ->
                        AsyncImage(
                            model = post.photoUrl,
                            contentDescription = post.generalTags?.joinToString(),
                            contentScale = ContentScale.Crop,
                            modifier = Modifier
                                .aspectRatio(1f)
                                .clip(MaterialTheme.shapes.medium)
                                .clickable { onOpenPost(post.id) },
                        )
                    }
                }
            }
        }
    }
}
```

**Step 4: Build** — `./gradlew assembleDebug` → BUILD SUCCESSFUL. (Navigation wiring comes in Task 12; screen is verified on-device then.)

**Step 5: Commit** — `git commit -m "feat(android): gallery grid with Paging 3 and tag filter"`

---

## Task 10: Post Detail screen (read-only)

**Files:**
- Create: `gallery/PostDetailViewModel.kt`, `gallery/PostDetailScreen.kt`

**Step 1: `gallery/PostDetailViewModel.kt`**

```kotlin
package com.semant.gallery

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.semant.data.PostRepository
import com.semant.data.remote.PostDto
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

sealed interface PostDetailState {
    data object Loading : PostDetailState
    data class Loaded(val post: PostDto) : PostDetailState
    data class Error(val message: String) : PostDetailState
}

@HiltViewModel
class PostDetailViewModel @Inject constructor(
    private val repo: PostRepository,
    savedState: SavedStateHandle,
) : ViewModel() {
    private val postId: String = checkNotNull(savedState["postId"])
    private val _state = MutableStateFlow<PostDetailState>(PostDetailState.Loading)
    val state: StateFlow<PostDetailState> = _state

    init { load() }

    fun load() {
        _state.value = PostDetailState.Loading
        viewModelScope.launch {
            runCatching { repo.getPost(postId) }
                .onSuccess { _state.value = PostDetailState.Loaded(it) }
                .onFailure { _state.value = PostDetailState.Error(it.message ?: "Failed to load") }
        }
    }
}
```

**Step 2: `gallery/PostDetailScreen.kt`** — zoomable image with bounding-box overlay + metadata below:

```kotlin
package com.semant.gallery

import androidx.compose.foundation.gestures.rememberTransformableState
import androidx.compose.foundation.gestures.transformable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import coil.compose.AsyncImage
import com.semant.data.remote.PostDto
import com.semant.ui.theme.Terracotta

@Composable
fun PostDetailScreen(viewModel: PostDetailViewModel = hiltViewModel()) {
    when (val s = viewModel.state.collectAsState().value) {
        PostDetailState.Loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            CircularProgressIndicator()
        }
        is PostDetailState.Error -> Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center) {
            Text(s.message); Spacer(Modifier.height(8.dp))
            Button(onClick = viewModel::load) { Text("Retry") }
        }
        is PostDetailState.Loaded -> PostDetail(s.post)
    }
}

@Composable
private fun PostDetail(post: PostDto) {
    var scale by remember { mutableFloatStateOf(1f) }
    var offset by remember { mutableStateOf(Offset.Zero) }
    val transformState = rememberTransformableState { zoom, pan, _ ->
        scale = (scale * zoom).coerceIn(1f, 5f)
        offset += pan
    }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        AsyncImage(
            model = post.photoUrl,
            contentDescription = null,
            contentScale = ContentScale.FillWidth,
            modifier = Modifier
                .fillMaxWidth()
                .graphicsLayer(scaleX = scale, scaleY = scale, translationX = offset.x, translationY = offset.y)
                .transformable(transformState),
        )
        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            post.generalTags?.takeIf { it.isNotEmpty() }?.let { tags ->
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    tags.take(6).forEach { AssistChip(onClick = {}, label = { Text(it) }) }
                }
            }
            (post.instagramHandles ?: listOfNotNull(post.instagramHandle)).takeIf { it.isNotEmpty() }?.let {
                Text("@" + it.joinToString(", @"), style = MaterialTheme.typography.bodyMedium, color = Terracotta)
            }
            post.textBlocks.forEach { block ->
                Text(block.content, style = when (block.type) {
                    "h1" -> MaterialTheme.typography.headlineMedium
                    "quote" -> MaterialTheme.typography.titleLarge
                    else -> MaterialTheme.typography.bodyLarge
                })
            }
            post.boundingBoxTags?.takeIf { it.isNotEmpty() }?.let { boxes ->
                Text("Regions", style = MaterialTheme.typography.titleMedium)
                boxes.keys.forEach { Text("· $it", style = MaterialTheme.typography.bodyMedium) }
            }
            post.localContext?.get("commentary")?.let {
                Text("Unconcealment", style = MaterialTheme.typography.titleMedium)
                Text(it.toString().trim('"'), style = MaterialTheme.typography.bodyLarge)
            }
        }
    }
}
```

(Bounding boxes are listed as text in Phase 1; drawing them over the zoomable image is Phase 2 work alongside editing. YAGNI.)

**Step 3: Build.** **Step 4: Commit** — `git commit -m "feat(android): post detail screen (zoomable image, tags, text blocks, context)"`

---

## Task 11: Queue screen

**Files:**
- Create: `queue/QueueViewModel.kt`, `queue/QueueScreen.kt`

**Step 1: `queue/QueueViewModel.kt`**

```kotlin
package com.semant.queue

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.semant.capture.CaptureRepository
import com.semant.data.local.CaptureDao
import com.semant.data.local.QueuedCapture
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class QueueViewModel @Inject constructor(
    dao: CaptureDao,
    private val captures: CaptureRepository,
) : ViewModel() {
    val items = dao.observeAll().stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
    val activeCount = dao.observeActiveCount().stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), 0)

    fun retry(id: Long) = viewModelScope.launch { captures.retry(id) }
    fun remove(capture: QueuedCapture) = viewModelScope.launch { captures.remove(capture) }
}
```

**Step 2: `queue/QueueScreen.kt`**

```kotlin
package com.semant.queue

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import coil.compose.AsyncImage
import com.semant.data.local.CaptureStatus
import java.io.File

@Composable
fun QueueScreen(viewModel: QueueViewModel = hiltViewModel()) {
    val items by viewModel.items.collectAsState()

    Column(Modifier.fillMaxSize()) {
        Text("Queue", style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.padding(start = 20.dp, top = 16.dp, bottom = 8.dp))

        if (items.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("Nothing queued — share an image to Semant from any app",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            return
        }

        LazyColumn(contentPadding = PaddingValues(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(items, key = { it.id }) { capture ->
                Card {
                    Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        AsyncImage(
                            model = capture.localFilePath?.let { File(it) } ?: capture.sourceUrl,
                            contentDescription = null,
                            contentScale = ContentScale.Crop,
                            modifier = Modifier.size(56.dp).clip(MaterialTheme.shapes.small),
                        )
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text(capture.tags.ifBlank { "untagged" }, style = MaterialTheme.typography.titleMedium)
                            Text(
                                when (capture.status) {
                                    CaptureStatus.PENDING -> "Waiting for network…"
                                    CaptureStatus.UPLOADING -> "Uploading…"
                                    CaptureStatus.DONE -> "Uploaded"
                                    CaptureStatus.FAILED -> "Failed: ${capture.lastError ?: "unknown error"}"
                                },
                                style = MaterialTheme.typography.bodyMedium,
                                color = if (capture.status == CaptureStatus.FAILED) MaterialTheme.colorScheme.error
                                        else MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        if (capture.status == CaptureStatus.FAILED) {
                            IconButton(onClick = { viewModel.retry(capture.id) }) {
                                Icon(Icons.Default.Refresh, contentDescription = "Retry")
                            }
                        }
                        IconButton(onClick = { viewModel.remove(capture) }) {
                            Icon(Icons.Default.Delete, contentDescription = "Delete")
                        }
                    }
                }
            }
        }
    }
}
```

**Step 3: Build.** **Step 4: Commit** — `git commit -m "feat(android): upload queue screen with retry/delete"`

---

## Task 12: Settings screen + navigation shell

**Files:**
- Create: `settings/SettingsViewModel.kt`, `settings/SettingsScreen.kt`, `ui/SemantNavHost.kt`
- Modify: `MainActivity.kt`

**Step 1: `settings/SettingsViewModel.kt`**

```kotlin
package com.semant.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.semant.data.SettingsRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val settings: SettingsRepository,
    private val client: OkHttpClient,
) : ViewModel() {
    val baseUrl = settings.baseUrl.stateIn(viewModelScope, SharingStarted.Eagerly, SettingsRepository.DEFAULT_BASE_URL)
    val apiKey = settings.apiKey.stateIn(viewModelScope, SharingStarted.Eagerly, "")

    private val _testResult = MutableStateFlow<String?>(null)
    val testResult: StateFlow<String?> = _testResult

    fun saveBaseUrl(v: String) = viewModelScope.launch { settings.setBaseUrl(v) }
    fun saveApiKey(v: String) = viewModelScope.launch { settings.setApiKey(v) }

    fun testConnection() {
        _testResult.value = "Testing…"
        viewModelScope.launch {
            _testResult.value = withContext(Dispatchers.IO) {
                runCatching {
                    // BaseUrlInterceptor rewrites the host; path is what matters
                    val res = client.newCall(Request.Builder().url("http://localhost/health").build()).execute()
                    if (res.isSuccessful) "Connected ✓" else "Server said ${res.code}"
                }.getOrElse { "Failed: ${it.message}" }
            }
        }
    }
}
```

**Step 2: `settings/SettingsScreen.kt`**

```kotlin
package com.semant.settings

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

@Composable
fun SettingsScreen(viewModel: SettingsViewModel = hiltViewModel()) {
    val savedBaseUrl by viewModel.baseUrl.collectAsState()
    val savedApiKey by viewModel.apiKey.collectAsState()
    val testResult by viewModel.testResult.collectAsState()

    var baseUrl by remember(savedBaseUrl) { mutableStateOf(savedBaseUrl) }
    var apiKey by remember(savedApiKey) { mutableStateOf(savedApiKey) }

    Column(Modifier.fillMaxSize().padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Settings", style = MaterialTheme.typography.headlineMedium)
        OutlinedTextField(value = baseUrl, onValueChange = { baseUrl = it },
            label = { Text("Backend URL") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        OutlinedTextField(value = apiKey, onValueChange = { apiKey = it },
            label = { Text("API key") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { viewModel.saveBaseUrl(baseUrl); viewModel.saveApiKey(apiKey) }) { Text("Save") }
            OutlinedButton(onClick = { viewModel.saveBaseUrl(baseUrl); viewModel.saveApiKey(apiKey); viewModel.testConnection() }) {
                Text("Test connection")
            }
        }
        testResult?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
    }
}
```

**Step 3: `ui/SemantNavHost.kt`** — bottom nav (Gallery / Queue / Settings) + detail route:

```kotlin
package com.semant.ui

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CloudUpload
import androidx.compose.material.icons.filled.GridView
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.compose.*
import com.semant.gallery.GalleryScreen
import com.semant.gallery.PostDetailScreen
import com.semant.queue.QueueScreen
import com.semant.queue.QueueViewModel
import com.semant.settings.SettingsScreen

private data class Dest(val route: String, val label: String, val icon: androidx.compose.ui.graphics.vector.ImageVector)

@Composable
fun SemantNavHost(startOnQueue: Boolean = false) {
    val nav = rememberNavController()
    val dests = listOf(
        Dest("gallery", "Gallery", Icons.Default.GridView),
        Dest("queue", "Queue", Icons.Default.CloudUpload),
        Dest("settings", "Settings", Icons.Default.Settings),
    )
    val queueViewModel: QueueViewModel = hiltViewModel()
    val activeCount by queueViewModel.activeCount.collectAsState()

    Scaffold(bottomBar = {
        NavigationBar {
            val backStack by nav.currentBackStackEntryAsState()
            val current = backStack?.destination?.route
            dests.forEach { dest ->
                NavigationBarItem(
                    selected = current == dest.route,
                    onClick = { nav.navigate(dest.route) { popUpTo("gallery"); launchSingleTop = true } },
                    label = { Text(dest.label) },
                    icon = {
                        if (dest.route == "queue" && activeCount > 0)
                            BadgedBox(badge = { Badge { Text("$activeCount") } }) { Icon(dest.icon, dest.label) }
                        else Icon(dest.icon, dest.label)
                    },
                )
            }
        }
    }) { padding ->
        NavHost(nav, startDestination = if (startOnQueue) "queue" else "gallery", Modifier.padding(padding)) {
            composable("gallery") { GalleryScreen(onOpenPost = { nav.navigate("post/$it") }) }
            composable("post/{postId}") { PostDetailScreen() }
            composable("queue") { QueueScreen() }
            composable("settings") { SettingsScreen() }
        }
    }
}
```

**Step 4: `MainActivity.kt`** — replace body:

```kotlin
package com.semant

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import com.semant.ui.SemantNavHost
import com.semant.ui.theme.SemantTheme
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= 33) {
            registerForActivityResult(ActivityResultContracts.RequestPermission()) {}
                .launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        val startOnQueue = intent.getBooleanExtra("open_queue", false)
        setContent { SemantTheme { SemantNavHost(startOnQueue = startOnQueue) } }
    }
}
```

**Step 5: Build + run on device/emulator** — `./gradlew installDebug`. Verify all three tabs render, Settings saves and "Test connection" reaches the backend (`API_KEY` set → save key first, expect "Connected ✓").

**Step 6: Run the full unit test suite** — `./gradlew testDebugUnitTest` → all pass.

**Step 7: Commit** — `git commit -m "feat(android): settings screen and bottom-nav shell"`

---

## Task 13: End-to-end manual verification (device required)

Checklist — run against the local backend first (`API_KEY=testkey uvicorn backend.main:app --port 5007`, phone on same Wi-Fi, base URL `http://<machine-ip>:5007`; Android blocks cleartext HTTP by default — for local testing either use the Render URL or temporarily add `android:usesCleartextTraffic="true"` to `<application>` and remove before release):

1. **WhatsApp** → open an image → Share → Semant → tag → Save → appears in Queue → status becomes Uploaded → visible in the web gallery.
2. **Twitter/X** → share an image post → Semant. If Twitter shares a page URL (not image bytes), the queue item will fail with the server's error — confirm the failure is visible and readable in Queue, not silent.
3. **Chrome** → long-press an image → Share image → Semant → uploads as bytes.
4. **Chrome** → share a direct image URL (open image in new tab → share) → uploads via `upload-from-url`.
5. **Multi-image share** from Google Photos (select 3) → 3 queue rows → 3 posts.
6. **Airplane mode** → share an image → Save → Queue shows "Waiting for network…" → disable airplane mode → auto-uploads.
7. **Wrong API key** in Settings → gallery shows the error state pointing at Settings; fix key → Retry works.
8. **Gallery** → tag filter chips narrow results; tap post → detail shows image, tags, text blocks; pinch zoom works.

Record any failures as bugs; fix before merging. When done:

```bash
git add -A && git commit -m "chore(android): phase 1 verification fixes"
```

---

## Out of scope (Phase 2+)

- Aletheia dialogue, annotation editing/overlay drawing, capture-time "interpret now"
- Epics/Research/Personas views
- Fonts polish, launcher icon design, release signing + minification, Play Store
- Backend: per-device keys, rate limiting
