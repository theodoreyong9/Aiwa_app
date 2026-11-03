package com.aiwa.app.home

import android.webkit.WebView
import org.json.JSONArray

/**
 * The buttons of the page on the screen, read by the application itself (a visited page has no bridge to the application and sends nothing): the voice can then name
 * and press them. The list is the visible buttons and links of the page by their text (or by `data-aiwa-voice`); a link that leaves the page is not in it.
 * The script only reads; the page could lie about its names, which is no more than what it shows.
 */
object ControlsJs {
    private const val READ = """(function(){
function plain(t){return String(t||'').toLowerCase().replace(/œ/g,'oe').normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/[^a-z0-9 ]+/g,' ').replace(/\s+/g,' ').trim();}
function inside(a){var h=a.getAttribute('href')||'';if(h.charAt(0)==='#')return true;try{var u=new URL(a.href,location.href);return u.origin!=='null'&&u.origin===location.origin;}catch(e){return false;}}
function nodes(){var out=[],seen={};[].slice.call(document.querySelectorAll('[data-aiwa-voice],button,a[href],[role="button"],input[type="submit"],input[type="button"],summary')).forEach(function(n){
 if(n.closest('.aiwa-slot,.aiwa-sheet,.aiwa-dock,[data-aiwa-slot],[data-aiwa-button]')||n.hasAttribute('data-aiwa-novoice')||(n.tagName==='A'&&!inside(n)))return;
 var words=(n.getAttribute('data-aiwa-voice')||'').split('|').map(function(w){return w.trim().slice(0,30);}).filter(Boolean).slice(0,5);
 var name=(n.getAttribute('aria-label')||n.textContent||n.value||n.title||words[0]||'').replace(/\s+/g,' ').trim().slice(0,40);
 if(!name||seen[plain(name)])return;if(!words.length&&n.getClientRects().length===0)return;seen[plain(name)]=1;out.push({node:n,name:name,words:words});});return out.slice(0,40);}
window.__aiwaPress=function(name){var want=plain(name),hit=null;nodes().forEach(function(c){if(!hit&&(plain(c.name)===want||c.words.some(function(w){return plain(w)===want;})))hit=c;});
 if(!hit)return false;try{hit.node.scrollIntoView({block:'center'});}catch(e){}hit.node.click();return true;};
return JSON.stringify(nodes().map(function(c){return{name:c.name,words:c.words};}));})()"""

    /** Reads the buttons of the page in front and hands them to `onList` (an empty list when the page says nothing). */
    fun read(web: WebView, onList: (JSONArray) -> Unit) {
        web.evaluateJavascript(READ) { raw ->
            val list = try {
                // evaluateJavascript gives a JSON string literal holding the JSON text
                JSONArray(org.json.JSONTokener(raw ?: "null").nextValue() as? String ?: "[]")
            } catch (err: Exception) { JSONArray() }
            onList(list)
        }
    }
}
