package com.aiwa.app.widget

/** Why the Agent tab of the widget is red, in words (set each time the widget is drawn): a red tab with no way to know the reason is worse than none. */
object WidgetAlert {
    @Volatile var reasons: List<String> = emptyList()
}
