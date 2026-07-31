pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic

ComboBox {
    id: root

    required property var theme

    implicitHeight: 40
    leftPadding: 12
    rightPadding: 34
    focusPolicy: Qt.StrongFocus

    delegate: ItemDelegate {
        id: option

        required property int index

        width: root.width - 8
        height: 38
        highlighted: root.highlightedIndex === index

        contentItem: Text {
            text: root.textAt(option.index)
            color: root.theme.text
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeLabel
        }

        background: Rectangle {
            radius: root.theme.radiusSmall
            color: option.highlighted ? root.theme.accentSoft : "transparent"
        }
    }

    contentItem: Text {
        text: root.displayText
        color: root.enabled ? root.theme.text : root.theme.placeholderText
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        font.family: root.theme.fontFamily
        font.pixelSize: root.theme.typeLabel
    }

    indicator: Canvas {
        id: dropdownIndicator
        x: root.width - width - 10
        y: (root.height - height) / 2
        width: 14
        height: 8
        contextType: "2d"

        onPaint: {
            const ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            ctx.strokeStyle = root.enabled
                              ? root.theme.secondaryText
                              : root.theme.placeholderText
            ctx.lineWidth = 1.5
            ctx.lineCap = "round"
            ctx.lineJoin = "round"
            ctx.beginPath()
            ctx.moveTo(2, 2)
            ctx.lineTo(width / 2, height - 2)
            ctx.lineTo(width - 2, 2)
            ctx.stroke()
        }
    }

    Connections {
        target: root

        function onEnabledChanged() {
            dropdownIndicator.requestPaint()
        }
    }

    background: Rectangle {
        radius: root.theme.radiusControl
        color: root.down ? root.theme.controlPressed
               : root.hovered ? root.theme.controlHover
                              : root.theme.control
        border.color: root.activeFocus ? root.theme.accent : "transparent"
        border.width: root.activeFocus ? 2 : 0
        Behavior on color {
            ColorAnimation { duration: root.theme.motionFast }
        }
    }

    popup: Popup {
        y: root.height + 4
        width: root.width
        implicitHeight: Math.min(contentItem.implicitHeight + 8, 248)
        padding: 4

        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: root.popup.visible ? root.delegateModel : null
            currentIndex: root.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator { }
        }

        background: Rectangle {
            radius: root.theme.radiusCard
            color: root.theme.surfaceRaised
            border.color: root.theme.separator
            border.width: 1
        }
    }
}
