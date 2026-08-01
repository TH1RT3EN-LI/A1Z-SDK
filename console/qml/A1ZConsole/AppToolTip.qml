import QtQuick
import QtQuick.Controls.Basic

ToolTip {
    id: root

    required property var theme
    property int maximumTextWidth: 520

    delay: 250
    timeout: 12000
    leftPadding: 12
    rightPadding: 12
    topPadding: 9
    bottomPadding: 9

    TextMetrics {
        id: textMetrics
        text: root.text
        font: toolTipText.font
    }

    contentItem: Text {
        id: toolTipText
        text: root.text
        textFormat: Text.PlainText
        color: root.theme.text
        wrapMode: Text.Wrap
        width: Math.min(root.maximumTextWidth,
                        Math.max(80, textMetrics.advanceWidth))
        font.family: root.theme.fontFamily
        font.pixelSize: root.theme.typeCaption
    }

    background: Rectangle {
        radius: root.theme.radiusControl
        color: root.theme.toolbar
        border.width: 1
        border.color: root.theme.borderStrong
    }
}
