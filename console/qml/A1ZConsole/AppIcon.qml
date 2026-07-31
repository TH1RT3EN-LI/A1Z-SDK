import QtQuick

Canvas {
    id: root

    property string name: "activity"
    property color color: "#FF000000"
    property real strokeWidth: 1.5

    implicitWidth: 18
    implicitHeight: 18
    antialiasing: true

    onNameChanged: requestPaint()
    onColorChanged: requestPaint()
    onStrokeWidthChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()

    onPaint: {
        const ctx = getContext("2d")
        const sx = width / 18
        const sy = height / 18

        ctx.clearRect(0, 0, width, height)
        ctx.save()
        ctx.scale(sx, sy)
        ctx.strokeStyle = root.color
        ctx.fillStyle = root.color
        ctx.lineWidth = root.strokeWidth
        ctx.lineCap = "round"
        ctx.lineJoin = "round"

        if (root.name === "activity") {
            ctx.beginPath()
            ctx.arc(9, 10, 5.5, Math.PI * 0.88, Math.PI * 2.12)
            ctx.stroke()
            ctx.beginPath()
            ctx.moveTo(9, 10)
            ctx.lineTo(12.6, 7.4)
            ctx.stroke()
            ctx.beginPath()
            ctx.arc(9, 10, 1, 0, Math.PI * 2)
            ctx.fill()
        } else if (root.name === "sliders") {
            const rows = [[4.8, 4.5], [12.2, 9], [7.2, 13.5]]
            for (let i = 0; i < rows.length; ++i) {
                ctx.beginPath()
                ctx.moveTo(2.5, rows[i][1])
                ctx.lineTo(15.5, rows[i][1])
                ctx.stroke()
                ctx.beginPath()
                ctx.arc(rows[i][0], rows[i][1], 1.5, 0, Math.PI * 2)
                ctx.fill()
            }
        } else if (root.name === "target") {
            ctx.beginPath()
            ctx.arc(9, 9, 5, 0, Math.PI * 2)
            ctx.stroke()
            ctx.beginPath()
            ctx.arc(9, 9, 2, 0, Math.PI * 2)
            ctx.stroke()
            ctx.beginPath()
            ctx.moveTo(9, 1.5)
            ctx.lineTo(9, 4)
            ctx.moveTo(9, 14)
            ctx.lineTo(9, 16.5)
            ctx.moveTo(1.5, 9)
            ctx.lineTo(4, 9)
            ctx.moveTo(14, 9)
            ctx.lineTo(16.5, 9)
            ctx.stroke()
        } else if (root.name === "command") {
            ctx.beginPath()
            ctx.rect(2.5, 3.5, 13, 11)
            ctx.stroke()
            ctx.beginPath()
            ctx.moveTo(5.5, 7)
            ctx.lineTo(8, 9)
            ctx.lineTo(5.5, 11)
            ctx.moveTo(10, 11)
            ctx.lineTo(13, 11)
            ctx.stroke()
        } else {
            ctx.beginPath()
            ctx.moveTo(1.8, 10)
            ctx.lineTo(4.3, 10)
            ctx.lineTo(6.2, 5.5)
            ctx.lineTo(8.7, 13)
            ctx.lineTo(11, 7.3)
            ctx.lineTo(12.8, 10)
            ctx.lineTo(16.2, 10)
            ctx.stroke()
        }

        ctx.restore()
    }
}
